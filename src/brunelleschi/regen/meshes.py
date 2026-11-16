"""Display meshes of every element, regenerated only for elements whose inputs changed."""

from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from uuid import UUID

from brunelleschi.geometry.joins import Vec, WallLine
from brunelleschi.geometry.solids import Mesh, prism, wall_mesh
from brunelleschi.model import Project
from brunelleschi.regen.openings import OpeningGeometry
from brunelleschi.regen.walls import wall_geometry

# Thickness of the simple solids that stand for a door leaf and a window frame (the same
# as in the IFC export).
DOOR_LEAF_THICKNESS = 0.05
WINDOW_FRAME_THICKNESS = 0.10


@dataclass(frozen=True, slots=True)
class ElementMesh:
    element_id: UUID
    kind: str  # "wall", "door" or "window"
    mesh: Mesh


def _filling(o: OpeningGeometry, line: WallLine, thickness: float) -> Mesh:
    # The opening's plan corners span the wall thickness; shrink them across the wall.
    (c0, c1, c2, c3) = o.corners
    ratio = thickness / line.thickness

    def towards_axis(outer: Vec, other: Vec) -> tuple[Vec, Vec]:
        mx, my = (outer[0] + other[0]) / 2, (outer[1] + other[1]) / 2
        return (
            (mx + (outer[0] - mx) * ratio, my + (outer[1] - my) * ratio),
            (mx + (other[0] - mx) * ratio, my + (other[1] - my) * ratio),
        )

    a0, a3 = towards_axis(c0, c3)
    a1, a2 = towards_axis(c1, c2)
    return prism([a0, a1, a2, a3], o.z_bottom, o.z_top)


@dataclass
class MeshCache:
    entries: dict[UUID, tuple[object, ElementMesh]] = field(default_factory=dict)
    last_rebuilt: set[UUID] = field(default_factory=set)

    def update(self, project: Project) -> dict[UUID, ElementMesh]:
        geometry = wall_geometry(project)
        current: dict[UUID, ElementMesh] = {}
        self.last_rebuilt = set()
        by_host: dict[UUID, list[OpeningGeometry]] = {}
        for o in geometry.openings.values():
            by_host.setdefault(o.host_id, []).append(o)
        for wall in project.walls:
            line = geometry.lines[wall.id]
            corners = geometry.footprints[wall.id].corners
            cuts = []
            for e in project.hosted_in(wall.id):
                a, b = e.along()
                o = geometry.openings[e.id]
                cuts.append((a, b, o.z_bottom, o.z_top))
            key = (line, corners, tuple(sorted(cuts)))
            current[wall.id] = self._get(
                wall.id, "wall", key, partial(wall_mesh, line, corners, cuts)
            )
        for e in project.hosted:
            o = geometry.openings[e.id]
            line = geometry.lines[e.host_id]
            thickness = DOOR_LEAF_THICKNESS if e.kind == "door" else WINDOW_FRAME_THICKNESS
            element_key = (o.corners, o.z_bottom, o.z_top, line.thickness, e.kind)
            current[e.id] = self._get(
                e.id, e.kind, element_key, partial(_filling, o, line, thickness)
            )
        self.entries = {k: v for k, v in self.entries.items() if k in current}
        return current

    def _get(
        self, element_id: UUID, kind: str, key: object, build: Callable[[], Mesh]
    ) -> ElementMesh:
        entry = self.entries.get(element_id)
        if entry is not None and entry[0] == key:
            return entry[1]
        mesh = ElementMesh(element_id, kind, build())
        self.entries[element_id] = (key, mesh)
        self.last_rebuilt.add(element_id)
        return mesh


_caches: dict[int, tuple[weakref.ref[Project], MeshCache]] = {}


def mesh_cache_for(project: Project) -> MeshCache:
    key = id(project)
    entry = _caches.get(key)
    if entry is None or entry[0]() is not project:
        cache = MeshCache()
        _caches[key] = (weakref.ref(project, lambda _: _caches.pop(key, None)), cache)
        return cache
    return entry[1]


def element_meshes(project: Project) -> dict[UUID, ElementMesh]:
    """A mesh per wall, door and window, in model order, brought up to date."""
    return mesh_cache_for(project).update(project)
