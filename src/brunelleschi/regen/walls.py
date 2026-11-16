"""Wall joins and footprints of a project, regenerated incrementally."""

from __future__ import annotations

import weakref
from dataclasses import dataclass, field
from uuid import UUID

from shapely import Polygon

from brunelleschi.geometry.joins import (
    END,
    START,
    EndCorners,
    Join,
    JoinIssue,
    PointKey,
    Vec,
    WallLine,
    crossings,
    footprint,
    point_key,
    solve_point,
)
from brunelleschi.model import Project, Wall


@dataclass(frozen=True, slots=True)
class WallFootprint:
    """A wall's outline in plan, with its ends cut by the joins it takes part in."""

    wall_id: UUID
    corners: tuple[Vec, ...]  # counter-clockwise
    polygon: Polygon


@dataclass(frozen=True, slots=True)
class WallGeometry:
    """Joins, footprints and join problems of every wall in a project."""

    footprints: dict[UUID, WallFootprint]
    joins: tuple[Join, ...]
    issues: tuple[JoinIssue, ...]


def _line(project: Project, wall: Wall) -> WallLine:
    base, top = project.wall_z_range(wall)
    return WallLine(
        id=wall.id,
        start=(wall.start.x, wall.start.y),
        end=(wall.end.x, wall.end.y),
        thickness=wall.thickness,
        base_z=base,
        top_z=top,
    )


@dataclass
class WallGeometryCache:
    """Derived wall geometry of one project.

    ``last_recomputed`` holds the join points recomputed by the latest ``update``; the
    tests use it to check that a change regenerates only what it affects.
    """

    lines: dict[UUID, WallLine] = field(default_factory=dict)
    points: dict[PointKey, tuple[tuple[Join, ...], tuple[JoinIssue, ...]]] = field(
        default_factory=dict
    )
    ends: dict[tuple[UUID, int], EndCorners] = field(default_factory=dict)
    footprints: dict[UUID, WallFootprint] = field(default_factory=dict)
    issues_by_wall: dict[UUID, JoinIssue] = field(default_factory=dict)
    last_recomputed: set[PointKey] = field(default_factory=set)

    def update(self, project: Project) -> None:
        current = {w.id: _line(project, w) for w in project.walls}
        changed = {
            wid
            for wid in current.keys() | self.lines.keys()
            if current.get(wid) != self.lines.get(wid)
        }
        self.last_recomputed = set()
        if not changed:
            return

        # Join points that may differ: both ends of every changed wall, before and after,
        # and every wall end lying on a changed wall's centre line (possible tees).
        affected: set[PointKey] = set()
        for wid in changed:
            for line in (self.lines.get(wid), current.get(wid)):
                if line is None:
                    continue
                affected.add(point_key(line.start))
                affected.add(point_key(line.end))
                for other in current.values():
                    for p in (other.start, other.end):
                        if line.passes_through(p):
                            affected.add(point_key(p))

        all_lines = list(current.values())
        touched = set(changed)
        # First forget every cut end at an affected point (positions as they were), then
        # solve the points again with the walls as they are.
        for wid, which in list(self.ends):
            old = self.lines.get(wid)
            if old is not None and point_key(old.endpoint(which)) in affected:
                del self.ends[(wid, which)]
                touched.add(wid)
        for key in affected:
            solution = solve_point(key, all_lines)
            if solution.joins or solution.issues:
                self.points[key] = (solution.joins, solution.issues)
            else:
                self.points.pop(key, None)
            for end_key, corners in solution.ends.items():
                self.ends[end_key] = corners
                touched.add(end_key[0])
        self.lines = current
        self.last_recomputed = affected

        for wid in touched:
            self.footprints.pop(wid, None)
            self.issues_by_wall.pop(wid, None)
            line = current.get(wid)
            if line is not None:
                self._footprint(line)

    def _footprint(self, line: WallLine) -> None:
        corners = footprint(line, self.ends.get((line.id, START)), self.ends.get((line.id, END)))
        polygon = Polygon(corners)
        if not polygon.is_valid or polygon.area <= 0:
            # The two cut ends cross each other (a very short wall between two joins).
            self.issues_by_wall[line.id] = JoinIssue(
                line.start,
                (line.id,),
                "the wall is too short for the joins at both ends; drawn with square ends",
            )
            corners = footprint(line, None, None)
            polygon = Polygon(corners)
        self.footprints[line.id] = WallFootprint(line.id, tuple(corners), polygon)

    def geometry(self) -> WallGeometry:
        joins = tuple(j for js, _ in self.points.values() for j in js)
        issues = [i for _, iss in self.points.values() for i in iss]
        issues += self.issues_by_wall.values()
        issues += crossings(list(self.lines.values()))
        return WallGeometry(
            footprints={wid: self.footprints[wid] for wid in self.lines},
            joins=tuple(sorted(joins, key=lambda j: (j.point, j.walls))),
            issues=tuple(sorted(issues, key=lambda i: (i.point, i.walls))),
        )


# One cache per live project. Keyed by identity: projects are mutable and unhashable.
_caches: dict[int, tuple[weakref.ref[Project], WallGeometryCache]] = {}


def cache_for(project: Project) -> WallGeometryCache:
    key = id(project)
    entry = _caches.get(key)
    if entry is None or entry[0]() is not project:
        cache = WallGeometryCache()
        _caches[key] = (weakref.ref(project, lambda _: _caches.pop(key, None)), cache)
        return cache
    return entry[1]


def wall_geometry(project: Project) -> WallGeometry:
    """Joins, footprints and join problems of every wall, brought up to date."""
    cache = cache_for(project)
    cache.update(project)
    return cache.geometry()
