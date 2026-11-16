"""IFC4 export: structure, relationships, stable ids, geometry and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.shape
import pytest

from brunelleschi import api
from brunelleschi.ifc import export_ifc, global_id, validate_ifc, write_ifc


@pytest.fixture
def house() -> api.Project:
    """Two levels, a 6 x 4 m room with a partition, a door, two windows, an upper wall."""
    p = api.new_project("Casa")
    api.add_level(p, "Piano terra", 0.0)
    api.add_level(p, "Primo piano", 3.0)
    api.add_level(p, "Copertura", 6.0)
    room = [(0, 0), (6, 0), (6, 4), (0, 4)]
    walls = [
        api.add_wall(p, c, room[(i + 1) % 4], 0.3, "Piano terra", top_level="Primo piano")
        for i, c in enumerate(room)
    ]
    api.add_wall(p, (3, 0), (3, 4), 0.12, "Piano terra", top_level="Primo piano")
    api.add_wall(p, (0, 0), (6, 0), 0.3, "Primo piano", top_level="Copertura")
    api.add_door(p, walls[0].id, 1.5, 0.9, 2.1, swing_side="left", hinge="start")
    api.add_window(p, walls[0].id, 4.5, 1.2, 1.4, 0.9)
    api.add_window(p, walls[2].id, 1.5, 1.0, 1.2, 1.0)
    return p


def by_name(f: Any, ifc_class: str) -> dict[str, Any]:
    return {e.Name: e for e in f.by_type(ifc_class)}


def ids(f: Any) -> dict[str, str]:
    return {e.GlobalId: e.is_a() for e in f.by_type("IfcRoot")}


def world_shape(entity: Any) -> Any:
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    shape: Any = ifcopenshell.geom.create_shape(settings, entity)
    return shape.geometry


# ---------------------------------------------------------------- structure


def test_spatial_structure(house: api.Project) -> None:
    f = export_ifc(house)
    (project,) = f.by_type("IfcProject")
    (site,) = f.by_type("IfcSite")
    (building,) = f.by_type("IfcBuilding")
    assert project.Name == "Casa"
    assert project.GlobalId == global_id(house.id)
    assert ifcopenshell.util.element.get_aggregate(site) == project
    assert ifcopenshell.util.element.get_aggregate(building) == site
    storeys = by_name(f, "IfcBuildingStorey")
    assert {n: s.Elevation for n, s in storeys.items()} == {
        "Piano terra": 0.0,
        "Primo piano": 3.0,
        "Copertura": 6.0,
    }
    for level in house.levels:
        storey = storeys[level.name]
        assert storey.GlobalId == global_id(level.id)
        assert ifcopenshell.util.element.get_aggregate(storey) == building
        z = ifcopenshell.util.placement.get_local_placement(storey.ObjectPlacement)[2][3]
        assert z == pytest.approx(level.elevation)


def test_units_are_metres(house: api.Project) -> None:
    f = export_ifc(house)
    (length,) = [u for u in f.by_type("IfcSIUnit") if u.UnitType == "LENGTHUNIT"]
    assert (length.Name, length.Prefix) == ("METRE", None)


def test_walls_are_contained_in_their_base_storey(house: api.Project) -> None:
    f = export_ifc(house)
    walls = {w.GlobalId: w for w in f.by_type("IfcWall")}
    assert len(walls) == 6
    for wall in house.walls:
        ifc_wall = walls[global_id(wall.id)]
        storey: Any = ifcopenshell.util.element.get_container(ifc_wall)
        assert storey.Name == house.level(wall.base_level_id).name


def test_openings_void_and_fillings_fill(house: api.Project) -> None:
    f = export_ifc(house)
    assert len(f.by_type("IfcOpeningElement")) == 3
    assert len(f.by_type("IfcRelVoidsElement")) == 3
    assert len(f.by_type("IfcRelFillsElement")) == 3
    fillings = {e.GlobalId: e for e in f.by_type("IfcDoor") + f.by_type("IfcWindow")}
    for element in house.hosted:
        filling = fillings[global_id(element.id)]
        assert filling.is_a() == ("IfcDoor" if element.kind == "door" else "IfcWindow")
        (fills,) = filling.FillsVoids
        opening = fills.RelatingOpeningElement
        (voids,) = opening.VoidsElements
        assert voids.RelatingBuildingElement.GlobalId == global_id(element.host_id)
        assert (filling.OverallWidth, filling.OverallHeight) == (element.width, element.height)
        host_storey = ifcopenshell.util.element.get_container(voids.RelatingBuildingElement)
        assert ifcopenshell.util.element.get_container(filling) == host_storey


@pytest.mark.parametrize(
    ("side", "hinge", "operation"),
    [
        ("left", "start", "SINGLE_SWING_LEFT"),
        ("left", "end", "SINGLE_SWING_RIGHT"),
        ("right", "start", "SINGLE_SWING_RIGHT"),
        ("right", "end", "SINGLE_SWING_LEFT"),
    ],
)
def test_door_operation_type(house: api.Project, side: str, hinge: str, operation: str) -> None:
    door = house.doors[0]
    api.modify_hosted(house, door.id, swing_side=side, hinge=hinge)
    (ifc_door,) = export_ifc(house).by_type("IfcDoor")
    assert ifc_door.OperationType == operation
    # The door's local y axis points to the side the leaf swings into.
    matrix = ifcopenshell.util.placement.get_local_placement(ifc_door.ObjectPlacement)
    assert matrix[1][1] == pytest.approx(1.0 if side == "left" else -1.0)


# ----------------------------------------------------------------- geometry


def test_wall_geometry_matches_the_model(house: api.Project) -> None:
    """IfcOpenShell's own evaluation of the exported solids: joined footprint x height,
    minus the openings."""
    f = export_ifc(house)
    geometry = api.wall_geometry(house)
    walls = {w.GlobalId: w for w in f.by_type("IfcWall")}
    for wall in house.walls:
        base, top = house.wall_z_range(wall)
        expected = geometry.footprints[wall.id].polygon.area * (top - base)
        for e in house.hosted_in(wall.id):
            expected -= e.width * wall.thickness * e.height
        shape = world_shape(walls[global_id(wall.id)])
        assert ifcopenshell.util.shape.get_volume(shape) == pytest.approx(expected)
        low, high = ifcopenshell.util.shape.get_bbox(ifcopenshell.util.shape.get_vertices(shape))
        assert (low[2], high[2]) == pytest.approx((base, top))


def test_door_sits_in_its_opening(house: api.Project) -> None:
    f = export_ifc(house)
    (door,) = f.by_type("IfcDoor")
    low, high = ifcopenshell.util.shape.get_bbox(
        ifcopenshell.util.shape.get_vertices(world_shape(door))
    )
    assert (low[0], high[0]) == pytest.approx((1.05, 1.95))
    assert (low[2], high[2]) == pytest.approx((0.0, 2.1))


def test_moving_a_level_changes_the_export(house: api.Project) -> None:
    api.set_level_elevation(house, "Primo piano", 3.2)
    f = export_ifc(house)
    assert by_name(f, "IfcBuildingStorey")["Primo piano"].Elevation == 3.2
    walls = {w.GlobalId: w for w in f.by_type("IfcWall")}
    wall = house.walls[0]
    _, high = ifcopenshell.util.shape.get_bbox(
        ifcopenshell.util.shape.get_vertices(world_shape(walls[global_id(wall.id)]))
    )
    assert high[2] == pytest.approx(3.2)


# ------------------------------------------------------------------ ids


def test_same_project_gives_the_same_global_ids(house: api.Project, tmp_path: Path) -> None:
    first = ids(export_ifc(house))
    assert ids(export_ifc(house)) == first
    api.save(house, tmp_path / "casa.bbim")
    assert ids(export_ifc(api.load(tmp_path / "casa.bbim"))) == first


def test_global_ids_are_unique(house: api.Project) -> None:
    f = export_ifc(house)
    roots = f.by_type("IfcRoot")
    assert len({e.GlobalId for e in roots}) == len(roots)


def test_adding_an_element_keeps_the_other_ids(house: api.Project) -> None:
    before = ids(export_ifc(house))
    api.add_wall(house, (0, 4), (0, 8), 0.3, "Piano terra", top_level="Primo piano")
    after = ids(export_ifc(house))
    assert set(before) <= set(after)
    assert len(after) == len(before) + 1


# ------------------------------------------------------------- validation


def test_export_is_valid_ifc4(house: api.Project) -> None:
    result = validate_ifc(export_ifc(house))
    assert result.rules_checked  # pytest is present, so EXPRESS rules ran too
    assert result.issues == ()


def test_empty_and_minimal_projects_are_valid() -> None:
    p = api.new_project("Empty")
    assert validate_ifc(export_ifc(p)).issues == ()
    api.add_level(p, "Ground", 0.0)
    api.add_wall(p, (0, 0), (1, 1), 0.1, "Ground", height=1.0)
    assert validate_ifc(export_ifc(p)).issues == ()


def test_validator_catches_errors(house: api.Project) -> None:
    """The zero above means something: a broken model is reported."""
    f = export_ifc(house)
    f.by_type("IfcDoor")[0].OverallWidth = -1.0  # IfcPositiveLengthMeasure
    issues = validate_ifc(f).issues
    assert issues
    assert any("IfcDoor" in i.instance or "OverallWidth" in i.message for i in issues)


def test_written_file_reads_back(house: api.Project, tmp_path: Path) -> None:
    path = tmp_path / "casa.ifc"
    write_ifc(house, path)
    f = ifcopenshell.open(str(path))
    assert f.schema == "IFC4"
    assert ids(f) == ids(export_ifc(house))
    assert validate_ifc(path).issues == ()
