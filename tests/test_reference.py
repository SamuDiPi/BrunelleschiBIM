"""Reading IFC files of others as references (no Qt)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from brunelleschi import api
from brunelleschi.ifc import write_ifc
from brunelleschi.ifc.reference import (
    ReferenceError,
    ReferenceStorey,
    load_reference,
    match_storeys,
    section,
)
from foreign_ifc import build_foreign_ifc


@pytest.fixture(scope="module")
def foreign(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_foreign_ifc(tmp_path_factory.mktemp("ext") / "strutture.ifc")


def test_a_millimetre_file_is_read_in_metres(foreign: Path) -> None:
    model = load_reference(foreign)
    assert model.schema == "IFC4"
    assert [(s.name, s.elevation) for s in model.storeys] == [("PT", 0.0), ("P1", 3.0)]
    by_name = {e.name: e for e in model.elements}
    assert sorted(by_name) == ["Muro A", "Muro B", "Pilastro", "Solaio"]
    low, high = by_name["Muro A"].vertices.min(axis=0), by_name["Muro A"].vertices.max(axis=0)
    assert low == pytest.approx([0, 0, 0])
    assert high == pytest.approx([5, 0.2, 3])
    column = by_name["Pilastro"].vertices
    assert column.max(axis=0) - column.min(axis=0) == pytest.approx([0.3, 0.3, 3.0])
    assert all(e.storey == model.storeys[0].global_id for e in model.elements)


def test_elements_without_geometry_are_counted(foreign: Path) -> None:
    model = load_reference(foreign)
    assert dict(model.without_geometry) == {"IfcFurniture": 1}
    assert not model.failed
    assert model.summary() == "4 elements, 1 without geometry"


def test_our_own_export_reads_back(tmp_path: Path) -> None:
    p = api.new_project("P")
    g = api.add_level(p, "G", 0.0)
    api.add_level(p, "F", 2.8)
    w = api.add_wall(p, (0, 0), (4, 0), 0.3, g.id, top_level="F")
    api.add_door(p, w.id, 1.0, 0.9, 2.1)
    write_ifc(p, tmp_path / "p.ifc")
    model = load_reference(tmp_path / "p.ifc")
    assert sorted(e.ifc_class for e in model.elements) == ["IfcDoor", "IfcWall"]
    assert [s.elevation for s in model.storeys] == [0.0, 2.8]


def test_load_is_deterministic(foreign: Path) -> None:
    a, b = load_reference(foreign), load_reference(foreign, threads=1)
    assert [e.global_id for e in a.elements] == [e.global_id for e in b.elements]


def test_bad_files(tmp_path: Path) -> None:
    with pytest.raises(ReferenceError, match="file not found"):
        load_reference(tmp_path / "missing.ifc")
    junk = tmp_path / "junk.ifc"
    junk.write_text("this is not STEP", encoding="utf-8")
    with pytest.raises(ReferenceError, match="not a readable IFC file"):
        load_reference(junk)


def test_match_storeys() -> None:
    storeys = [
        ReferenceStorey("a", "Piano terra", 0.02),  # by elevation, within 5 cm
        ReferenceStorey("b", "PRIMO PIANO", 3.4),  # by name
        ReferenceStorey("c", "Copertura", 9.0),  # nothing
    ]
    levels = [("G", "Ground", 0.0), ("F", "Primo piano", 3.0)]
    assert match_storeys(storeys, levels) == {"a": "G", "b": "F"}


def test_section_of_a_box() -> None:
    from brunelleschi.geometry.solids import prism

    box = prism([(0, 0), (2, 0), (2, 1), (0, 1)], 0.0, 3.0)
    segments = section(box.vertices, box.triangles, 1.2)
    points = segments.reshape(-1, 2)
    assert points.min(axis=0) == pytest.approx([0, 0])
    assert points.max(axis=0) == pytest.approx([2, 1])
    length = np.linalg.norm(segments[:, 1] - segments[:, 0], axis=1).sum()
    assert length == pytest.approx(6.0)  # the rectangle's perimeter
    assert len(section(box.vertices, box.triangles, 5.0)) == 0
