"""Openings cut by doors and windows in their host walls, and plan cuts through walls."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from shapely import MultiPolygon, Polygon

from brunelleschi.geometry.joins import Join, JoinIssue, JoinKind, Vec, WallLine
from brunelleschi.model import LENGTH_TOLERANCE, HostedElement, Project, short_id

# Area below which an overlap is numerical noise, in square metres.
AREA_TOLERANCE = 1e-9

# Cutters reach this far beyond the wall faces, so that cutting an opening out of a
# footprint never leaves slivers along the faces.
CUT_MARGIN = 1e-3


@dataclass(frozen=True, slots=True)
class OpeningGeometry:
    """The void a door or window makes in its host wall.

    ``corners`` is the opening in plan, across the full thickness of the wall,
    counter-clockwise; ``z_bottom`` and ``z_top`` are absolute elevations.
    """

    element_id: UUID
    host_id: UUID
    kind: str
    corners: tuple[Vec, ...]
    polygon: Polygon
    z_bottom: float
    z_top: float

    def spans(self, z: float) -> bool:
        return self.z_bottom < z < self.z_top


def _rectangle(line: WallLine, a: float, b: float, half: float) -> list[Vec]:
    (sx, sy), (dx, dy) = line.start, line.direction
    nx, ny = -dy * half, dx * half
    p, q = (sx + dx * a, sy + dy * a), (sx + dx * b, sy + dy * b)
    return [
        (p[0] - nx, p[1] - ny),
        (q[0] - nx, q[1] - ny),
        (q[0] + nx, q[1] + ny),
        (p[0] + nx, p[1] + ny),
    ]


def opening(element: HostedElement, line: WallLine) -> OpeningGeometry:
    a, b = element.along()
    corners = _rectangle(line, a, b, line.half)
    bottom, top = element.vertical()
    return OpeningGeometry(
        element_id=element.id,
        host_id=element.host_id,
        kind=element.kind,
        corners=tuple(corners),
        polygon=Polygon(corners),
        z_bottom=line.base_z + bottom,
        z_top=line.base_z + top,
    )


def openings(project: Project, lines: dict[UUID, WallLine]) -> dict[UUID, OpeningGeometry]:
    return {e.id: opening(e, lines[e.host_id]) for e in project.hosted}


def opening_issues(
    found: dict[UUID, OpeningGeometry],
    footprints: dict[UUID, Polygon],
    lines: dict[UUID, WallLine],
    joins: Sequence[Join],
) -> list[JoinIssue]:
    """Openings that run into the corner join at an end of their wall, or that a wall
    meeting their wall in a T stops against."""
    issues: list[JoinIssue] = []
    # Walls ending against each host, with where they touch it along its centre line.
    stops: dict[UUID, list[tuple[UUID, float, float]]] = {}
    for j in joins:
        if j.kind != JoinKind.TEE:
            continue
        stem = lines[j.walls[0]]
        for host_id in j.walls[1:]:
            host = lines[host_id]
            along = _along(host, j.point)
            sin = abs(_cross(stem.direction, host.direction)) or 1.0
            reach = stem.half / sin
            stops.setdefault(host_id, []).append((stem.id, along - reach, along + reach))
    for o in found.values():
        label = f"{o.kind} {short_id(o.element_id)}"
        centre = o.polygon.centroid
        point = (centre.x, centre.y)
        if o.polygon.difference(footprints[o.host_id]).area > AREA_TOLERANCE:
            issues.append(
                JoinIssue(
                    point,
                    (o.element_id, o.host_id),
                    f"{label} reaches into the join at an end of wall {short_id(o.host_id)}",
                )
            )
        host = lines[o.host_id]
        a, b = sorted((_along(host, o.corners[0]), _along(host, o.corners[1])))
        for stem_id, lo, hi in stops.get(o.host_id, []):
            stem = lines[stem_id]
            if (
                min(b, hi) - max(a, lo) > LENGTH_TOLERANCE
                and min(o.z_top, stem.top_z) - max(o.z_bottom, stem.base_z) > LENGTH_TOLERANCE
            ):
                issues.append(
                    JoinIssue(
                        point,
                        (o.element_id, stem_id),
                        f"{label} is blocked by wall {short_id(stem_id)}, which meets "
                        f"wall {short_id(o.host_id)} inside the opening",
                    )
                )
    return issues


def _cross(a: Vec, b: Vec) -> float:
    return a[0] * b[1] - a[1] * b[0]


def plan_cut(
    footprints: dict[UUID, Polygon],
    lines: dict[UUID, WallLine],
    found: dict[UUID, OpeningGeometry],
    z: float,
) -> dict[UUID, Polygon | MultiPolygon]:
    """Wall outlines cut by a horizontal plane at elevation ``z``: only walls that the
    plane crosses, with the openings that it crosses removed."""
    result: dict[UUID, Polygon | MultiPolygon] = {}
    for wall_id, shape in footprints.items():
        line = lines[wall_id]
        if not line.base_z < z < line.top_z:
            continue
        cut: Polygon | MultiPolygon = shape
        for o in found.values():
            if o.host_id == wall_id and o.spans(z):
                a = _along(line, o.corners[0])
                b = _along(line, o.corners[1])
                cutter = Polygon(_rectangle(line, a, b, line.half + CUT_MARGIN))
                difference = cut.difference(cutter)
                assert isinstance(difference, Polygon | MultiPolygon)
                cut = difference
        result[wall_id] = cut
    return result


def _along(line: WallLine, p: Vec) -> float:
    (sx, sy), (dx, dy) = line.start, line.direction
    return (p[0] - sx) * dx + (p[1] - sy) * dy
