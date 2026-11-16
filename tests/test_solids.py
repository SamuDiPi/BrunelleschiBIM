"""Display meshes of walls, doors and windows (no Qt)."""

from __future__ import annotations

from typing import Any

import ifcopenshell.geom
import ifcopenshell.util.shape
import numpy as np
import pytest

from brunelleschi import api
from brunelleschi.geometry.solids import prism
from brunelleschi.ifc import export_ifc, global_id
from brunelleschi.regen.meshes import element_meshes, mesh_cache_for


@pytest.fixture
def house() -> api.Project:
    """The M7 house plus a partition (two tees) and a high window."""
    p = api.new_project("P")
    g = api.add_level(p, "G", 0.0)
    f = api.add_level(p, "F", 3.0)
    c = [(0, 0), (6, 0), (6, 4), (0, 4)]
    w = [api.add_wall(p, s, c[(i + 1) % 4], 0.3, g.id, top_level=f.id) for i, s in enumerate(c)]
    api.add_wall(p, (3, 0), (3, 4), 0.12, g.id, top_level=f.id)
    api.add_door(p, w[0].id, 1.5, 0.9, 2.1)
    api.add_window(p, w[2].id, 4.5, 1.2, 1.4, 0.9)
    api.add_window(p, w[1].id, 2.0, 0.8, 0.6, 1.8)
    return p


def test_volumes_match_ifcopenshell(house: api.Project) -> None:
    """Our meshes and IfcOpenShell's evaluation of the IFC export are the same solids."""
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    f: Any = export_ifc(house)
    by_id = {e.GlobalId: e for e in f.by_type("IfcElement")}
    meshes = element_meshes(house)
    assert len(meshes) == 5 + 3
    for element_id, em in meshes.items():
        shape: Any = ifcopenshell.geom.create_shape(settings, by_id[global_id(element_id)])
        expected = ifcopenshell.util.shape.get_volume(shape.geometry)
        assert em.mesh.volume() == pytest.approx(expected, abs=1e-9), em.kind


def test_wall_extent(house: api.Project) -> None:
    meshes = element_meshes(house)
    low, high = meshes[house.walls[0].id].mesh.bounds()
    assert low == pytest.approx([-0.15, -0.15, 0.0])
    assert high == pytest.approx([6.15, 0.15, 3.0])


def test_only_changed_elements_are_rebuilt(house: api.Project) -> None:
    element_meshes(house)
    cache = mesh_cache_for(house)
    api.modify_hosted(house, house.doors[0].id, width=0.8)
    element_meshes(house)
    assert cache.last_rebuilt == {house.doors[0].id, house.walls[0].id}
    api.set_level_elevation(house, "F", 3.2)  # every wall reaches it
    meshes = element_meshes(house)
    assert {w.id for w in house.walls} <= cache.last_rebuilt
    assert meshes[house.walls[1].id].mesh.bounds()[1][2] == pytest.approx(3.2)
    element_meshes(house)
    assert cache.last_rebuilt == set()


def test_deleted_elements_leave_the_cache(house: api.Project) -> None:
    element_meshes(house)
    api.delete_wall(house, house.walls[0].id)  # with its door
    meshes = element_meshes(house)
    assert len(meshes) == 4 + 2
    assert len(mesh_cache_for(house).entries) == 6


def test_concave_prism() -> None:
    outline = [(0, 0), (4, 0), (4, 1), (1, 1), (1, 3), (0, 3)]  # an L, area 6
    mesh = prism(outline, 0.0, 2.0)
    assert mesh.volume() == pytest.approx(12.0)
    assert len(mesh.triangles) == 2 * 4 + 2 * 6  # two caps of 4 triangles, 6 sides


def test_meshes_are_closed(house: api.Project) -> None:
    """Every edge of a closed surface is shared by two triangles in opposite directions;
    internal faces between slices come in pairs too, so the count still balances."""
    for em in element_meshes(house).values():
        tris = em.mesh.triangles
        directed: dict[tuple[tuple[float, ...], tuple[float, ...]], int] = {}
        for t in tris:
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                key = (
                    tuple(np.round(em.mesh.vertices[a], 9)),
                    tuple(np.round(em.mesh.vertices[b], 9)),
                )
                directed[key] = directed.get(key, 0) + 1
        for (a, b), n in directed.items():
            assert directed.get((b, a), 0) >= 1, (em.kind, a, b, n)
