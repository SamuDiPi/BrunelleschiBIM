"""DXF export of plans (M14): units, layers, hatches, blocks, and CartesioCAD's reader."""

from __future__ import annotations

import math
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from ezdxf.filemanagement import readfile

from brunelleschi import api
from brunelleschi.cli import main
from brunelleschi.drawings.dxf import LAYERS, to_dxf
from brunelleschi.drawings.primitives import Arc, Insert, Line

REPO = Path(__file__).parent.parent


def cartesio_dxfinfo() -> Path | None:
    """CartesioCAD's command-line DXF reader, if it is built next to this repository."""
    configured = os.environ.get("CARTESIO_DXFINFO")
    candidates = [Path(configured)] if configured else []
    candidates.append(REPO.parent / "CartesioCAD" / "build" / "cartesio_dxfinfo.exe")
    candidates.append(REPO.parent / "CartesioCAD" / "build" / "cartesio_dxfinfo")
    return next((c for c in candidates if c.is_file()), None)


@pytest.fixture
def house() -> api.Project:
    """A room with a slanted wall, and doors in every swing/hinge combination."""
    p = api.new_project("Casa")
    g = api.add_level(p, "Piano terra", 0.0)
    f = api.add_level(p, "Primo piano", 3.0)
    c = [(0, 0), (8, 0), (8, 5), (0, 5)]
    w = [api.add_wall(p, s, c[(i + 1) % 4], 0.3, g.id, top_level=f.id) for i, s in enumerate(c)]
    slanted = api.add_wall(p, (8, 0), (11, 3), 0.2, g.id, top_level=f.id)
    api.add_door(p, w[0].id, 1.5, 0.9, 2.1, swing_side="left", hinge="start")
    api.add_door(p, w[0].id, 4.0, 0.8, 2.1, swing_side="left", hinge="end")
    api.add_door(p, w[0].id, 6.5, 0.9, 2.1, swing_side="right", hinge="start")
    api.add_door(p, w[2].id, 2.0, 0.9, 2.1, swing_side="right", hinge="end")
    api.add_door(p, slanted.id, 2.0, 0.8, 2.1, swing_side="right", hinge="end")
    api.add_window(p, w[1].id, 2.5, 1.2, 1.4, 0.9)
    api.add_window(p, slanted.id, 3.6, 0.6, 0.6, 1.0)
    api.add_window(p, w[3].id, 2.5, 1.0, 0.6, 1.6)  # above the cut: dashed outline
    return p


def plan(p: api.Project) -> Any:
    return api.plan_view(p, "Piano terra")


def test_units_and_layers(house: api.Project) -> None:
    doc = to_dxf(plan(house))
    assert doc.dxfversion == "AC1015"  # R2000, as CartesioCAD writes
    assert doc.header["$INSUNITS"] == 4  # millimetres
    for spec in LAYERS.values():
        layer = doc.layers.get(spec.name)
        assert (layer.color, layer.dxf.lineweight) == (spec.colour, spec.lineweight)
    assert doc.layers.get("OPENING-ABOVE").dxf.linetype == "DASHED"


def test_real_size_in_millimetres(house: api.Project) -> None:
    msp = to_dxf(plan(house)).modelspace()
    outlines: list[Any] = list(msp.query("LWPOLYLINE[layer=='WALL-CUT']"))
    xs = [x for e in outlines for x, *_ in e.get_points()]
    ys = [y for e in outlines for _, y, *_ in e.get_points()]
    assert (min(xs), max(xs)) == pytest.approx((-150.0, 11000 + 100 * math.sqrt(0.5)), abs=1)
    assert (min(ys), max(ys)) == pytest.approx((-150.0, 5150.0))


def test_cut_walls_are_solid_hatches(house: api.Project) -> None:
    drawing = plan(house)
    areas = [p for p in drawing.primitives if p.layer == "wall-cut"]
    msp = to_dxf(drawing).modelspace()
    hatches = msp.query("HATCH")
    assert len(hatches) == len(areas)
    for hatch, area in zip(hatches, areas, strict=True):
        assert hatch.dxf.solid_fill == 1
        assert hatch.dxf.layer == "WALL-CUT-HATCH"
        assert len(hatch.paths) == len(area.rings)


def test_doors_and_windows_are_shared_blocks(house: api.Project) -> None:
    doc = to_dxf(plan(house))
    names = sorted(b.name for b in doc.blocks if not b.name.startswith("*"))
    assert names == [
        "DOOR_800",
        "DOOR_800_M",
        "DOOR_900",
        "DOOR_900_M",
        "WINDOW_1200x300",
        "WINDOW_600x200",
    ]
    for insert in doc.modelspace().query("INSERT"):  # rotation only, never mirrored
        assert (insert.dxf.xscale, insert.dxf.yscale) == (1, 1)
    inserts = doc.modelspace().query("INSERT")
    assert len(inserts) == 5 + 2  # five doors, two windows cut by the plane
    assert {i.dxf.layer for i in inserts} == {"DOOR", "WINDOW"}
    door = doc.blocks.get("DOOR_900")
    assert sorted(e.dxftype() for e in door) == ["ARC", "LINE"]
    assert {e.dxf.layer for e in door} == {"DOOR", "DOOR-SWING"}


def _points(entity: Any) -> list[tuple[float, float]]:
    if entity.dxftype() == "LINE":
        return [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]
    if entity.dxftype() == "ARC":  # centre and end points in world coordinates
        c = entity.ocs().to_wcs(entity.dxf.center)
        return sorted([(c.x, c.y)] + [(p.x, p.y) for p in (entity.start_point, entity.end_point)])
    raise AssertionError(entity.dxftype())


def _ours(shape: Any) -> list[tuple[float, float]]:
    mm = [(x * 1000, y * 1000) for x, y in (shape.points if isinstance(shape, Line) else ())]
    if isinstance(shape, Arc):
        return sorted((x * 1000, y * 1000) for x, y in (shape.centre, shape.start, shape.end))
    return mm


def test_block_inserts_land_exactly_where_the_plan_draws(house: api.Project) -> None:
    """ezdxf's own expansion of every INSERT (rotation, mirroring, arcs) matches the shapes
    of our plan, for every swing and hinge combination and on a slanted wall."""
    drawing = plan(house)
    inserts = [p for p in drawing.primitives if isinstance(p, Insert)]
    assert {i.mirror for i in inserts} == {False, True}  # both cases are exercised
    msp = to_dxf(drawing).modelspace()
    for ours, theirs in zip(inserts, msp.query("INSERT"), strict=True):
        expected = sorted(_ours(s) for s in ours.expand())
        got = sorted(_points(e) for e in theirs.virtual_entities())
        assert len(expected) == len(got)
        for a, b in zip(expected, got, strict=True):
            flat_a = [v for point in a for v in point]
            flat_b = [v for point in b for v in point]
            assert flat_a == pytest.approx(flat_b, abs=1e-6), (ours.block.name, ours.mirror)


def test_cli_and_round_trip(house: api.Project, tmp_path: Path) -> None:
    project = tmp_path / "casa.bbim"
    api.save(house, project)
    out = tmp_path / "pianta.dxf"
    assert main(["plan", str(project), "Piano terra", str(out)]) == 0
    doc = readfile(out)
    assert doc.header["$INSUNITS"] == 4
    assert len(doc.modelspace().query("INSERT")) == 7
    assert not list(tmp_path.glob(".*.tmp"))
    with pytest.raises(OSError):
        api.write_plan_dxf(house, "Piano terra", tmp_path / "missing" / "x.dxf")


def test_cartesiocad_reads_it(house: api.Project, tmp_path: Path) -> None:
    """The real check: CartesioCAD's own DXF reader, run from the command line."""
    tool = cartesio_dxfinfo()
    if tool is None:
        pytest.skip("CartesioCAD's cartesio_dxfinfo is not built next to this repository")
    out = tmp_path / "pianta.dxf"
    api.write_plan_dxf(house, "Piano terra", out)
    result = subprocess.run(
        [str(tool), str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    text = result.stdout
    assert "inserimenti senza blocco: 0" in text
    assert "Ignorati" not in text
    counts = dict(re.findall(r"^\s+(\w+)\s+(\d+)$", text, re.MULTILINE))
    assert int(counts["Insert"]) == 7
    assert int(counts["Hatch"]) == len([p for p in plan(house).primitives if p.layer == "wall-cut"])
    blocks = int(re.search(r"blocchi: (\d+)", text).group(1))  # type: ignore[union-attr]
    assert blocks == 6
    low = re.search(r"Estensioni: \((-?[\d.]+), (-?[\d.]+)\)", text)
    assert low is not None and float(low.group(1)) == pytest.approx(-150)
