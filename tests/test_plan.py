"""Plan view and SVG output: what is drawn, paper and scale, determinism, golden files."""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import UUID

import pytest
from shapely import Polygon

from brunelleschi import api
from brunelleschi.cli import main
from brunelleschi.drawings.primitives import Arc, Area, Drawing, Line, arc_extreme_points

GOLDEN = Path(__file__).parent / "golden"
SVG = "{http://www.w3.org/2000/svg}"


def uid(n: int) -> UUID:
    return UUID(int=n)


@pytest.fixture
def house() -> api.Project:
    """Two rooms with split walls and a partition, a slanted wall, a low wall, two doors,
    three windows (one above the cut). Fixed ids, so the output is fully reproducible."""
    p = api.new_project("Prova pianta")
    api.add_level(p, "Piano terra", 0.0, level_id=uid(1))
    api.add_level(p, "Primo piano", 3.0, level_id=uid(2))
    pts = {"a": (0, 0), "b": (4, 0), "c": (9, 0), "d": (9, 6), "e": (4, 6), "f": (0, 6)}
    walls: dict[str, api.Wall] = {}
    for n, pair in enumerate(("ab", "bc", "cd", "de", "ef", "fa", "be"), start=10):
        s, e = pair[0], pair[1]
        thickness = 0.12 if s + e == "be" else 0.3
        walls[s + e] = api.add_wall(
            p, pts[s], pts[e], thickness, "Piano terra", top_level="Primo piano", wall_id=uid(n)
        )
    api.add_wall(p, (9, 3), (12, 5), 0.2, "Piano terra", top_level="Primo piano", wall_id=uid(20))
    api.add_wall(p, (5, 4), (8, 4), 0.1, "Piano terra", height=0.9, wall_id=uid(21))
    api.add_wall(p, (0, 0), (9, 0), 0.3, "Primo piano", height=2.7, wall_id=uid(22))
    api.add_door(p, walls["ab"].id, 1.5, 0.9, 2.1, door_id=uid(30))
    api.add_door(p, walls["be"].id, 3.0, 0.8, 2.1, swing_side="right", hinge="end", door_id=uid(31))
    api.add_window(p, walls["bc"].id, 2.5, 1.4, 1.4, 0.9, window_id=uid(40))
    api.add_window(p, walls["ef"].id, 2.0, 0.8, 0.6, 1.6, window_id=uid(41))
    api.add_window(p, walls["cd"].id, 4.5, 1.0, 1.2, 1.0, window_id=uid(42))
    return p


def layer(drawing: Drawing, name: str) -> list[Area | Line | Arc]:
    return [p for p in drawing.flat() if p.layer == name]


def close(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return math.isclose(a[0], b[0], abs_tol=1e-9) and math.isclose(a[1], b[1], abs_tol=1e-9)


# --------------------------------------------------------------- the view


def test_cut_walls_form_one_mass(house: api.Project) -> None:
    drawing = api.plan_view(house, "Piano terra")
    areas = [a for a in layer(drawing, "wall-cut") if isinstance(a, Area)]
    assert all(a.element is None for a in areas)  # merged: no longer one area per wall
    outlines = layer(drawing, "wall-cut-outline")
    assert len(outlines) == sum(len(a.rings) for a in areas)
    # Merging loses and adds nothing: its area is the sum of the walls' cut areas.
    merged = sum(Polygon(a.rings[0], a.rings[1:]).area for a in areas)
    per_wall = sum(s.area for s in api.wall_geometry(house).plan_cut(1.2).values())
    assert merged == pytest.approx(per_wall)
    # Only ground floor walls are cut at 1.20: the upper wall starts at 3.00.
    assert uid(22) not in api.wall_geometry(house).plan_cut(1.2)


def test_door_leaf_and_swing(house: api.Project) -> None:
    drawing = api.plan_view(house, "Piano terra")
    doors = {p.element: p for p in layer(drawing, "door")}
    swings = {p.element: p for p in layer(drawing, "door-swing")}
    # Door 30: wall (0,0)->(4,0), centre 1.5, 0.9 wide, opens left (+y), hinge at the start.
    leaf = doors[uid(30)]
    assert isinstance(leaf, Line)
    assert close(leaf.points[0], (1.05, 0.15))
    assert close(leaf.points[1], (1.05, 1.05))
    arc = swings[uid(30)]
    assert isinstance(arc, Arc)
    assert close(arc.centre, (1.05, 0.15))
    assert close(arc.end, (1.95, 0.15))
    # Door 31: wall (4,0)->(4,6), opens right (+x), hinge at the end jamb (y = 3.4).
    leaf = doors[uid(31)]
    assert isinstance(leaf, Line)
    assert close(leaf.points[0], (4.06, 3.4))
    assert close(leaf.points[1], (4.86, 3.4))


def test_windows(house: api.Project) -> None:
    drawing = api.plan_view(house, "Piano terra")
    window_lines = layer(drawing, "window")
    assert {p.element for p in window_lines} == {uid(40), uid(42)}
    assert len(window_lines) == 6  # two faces and the glass line each
    (above,) = layer(drawing, "opening-above")  # window 41, sill 1.6 > cut 1.2
    assert above.element == uid(41)


def test_low_walls_are_seen_from_above(house: api.Project) -> None:
    drawing = api.plan_view(house, "Piano terra")
    (low,) = layer(drawing, "wall-projection")
    assert low.element == uid(21)


def test_cut_height_changes_what_is_cut(house: api.Project) -> None:
    high = api.plan_view(house, "Piano terra", cut_height=2.15)
    assert layer(high, "door") == []  # doors are 2.10 high: above them the wall is solid
    assert {p.element for p in layer(high, "window")} == {uid(40), uid(41), uid(42)}
    assert layer(high, "opening-above") == []
    low = api.plan_view(house, "Piano terra", cut_height=0.5)
    assert {p.element for p in layer(low, "wall-projection")} == set()  # the low wall is cut
    assert layer(low, "window") == []
    assert len(layer(low, "opening-above")) == 3


def test_upper_level(house: api.Project) -> None:
    drawing = api.plan_view(house, "Primo piano")
    assert len(layer(drawing, "wall-cut")) == 1
    assert layer(drawing, "door") == []


def test_arc_extent() -> None:
    quarter = Arc("door-swing", (0, 0), (1, 0), (0, 1))
    pts = arc_extreme_points(quarter)
    assert max(p[0] for p in pts) == pytest.approx(1)
    assert max(p[1] for p in pts) == pytest.approx(1)
    assert min(p[0] for p in pts) == pytest.approx(0)
    across = Arc("door-swing", (0, 0), (1, 1), (-1, 1))  # passes through (0, sqrt 2)
    assert max(p[1] for p in arc_extreme_points(across)) == pytest.approx(math.sqrt(2))


# ------------------------------------------------------------ paper, scale


@pytest.mark.parametrize(
    ("paper", "portrait", "size"),
    [
        ("A4", False, ("297mm", "210mm")),
        ("A4", True, ("210mm", "297mm")),
        ("A3", False, ("420mm", "297mm")),
        ("A1", False, ("841mm", "594mm")),
        ("A0", True, ("841mm", "1189mm")),
    ],
)
def test_paper_size(house: api.Project, paper: str, portrait: bool, size: tuple[str, str]) -> None:
    svg = ET.fromstring(api.plan_svg(house, "Piano terra", api.Sheet(paper, portrait, 100)))
    assert (svg.get("width"), svg.get("height")) == size
    w, h = (s.removesuffix("mm") for s in size)
    assert svg.get("viewBox") == f"0 0 {w} {h}"


@pytest.mark.parametrize("scale", [20, 50, 100])
def test_scale_gives_paper_millimetres(scale: int) -> None:
    p = api.new_project("P")
    api.add_level(p, "G", 0.0)
    api.add_wall(p, (0, 0), (6, 0), 0.3, "G", height=3)  # 6 m x 0.3 m
    svg = ET.fromstring(api.plan_svg(p, "G", api.Sheet("A1", scale=scale)))
    path = next(svg.iter(f"{SVG}path"))  # the poche; the outline follows
    numbers = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", path.get("d", ""))]
    xs, ys = numbers[0::2], numbers[1::2]
    assert max(xs) - min(xs) == pytest.approx(6000 / scale)
    assert max(ys) - min(ys) == pytest.approx(300 / scale)


def test_drawing_is_centred(house: api.Project) -> None:
    drawing = api.plan_view(house, "Piano terra")
    x0, y0, x1, y1 = drawing.extent() or (0, 0, 0, 0)
    svg = ET.fromstring(api.plan_svg(house, "Piano terra", api.Sheet("A3", scale=50)))
    numbers: list[float] = []
    for path in svg.iter(f"{SVG}path"):
        d = re.sub(r"A\S+ \S+ 0 0 [01] ", "", path.get("d", ""))  # drop arc radii and flags
        numbers += [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", d)]
    xs, ys = numbers[0::2], numbers[1::2]
    assert (min(xs) + max(xs)) / 2 == pytest.approx(210, abs=0.01)
    assert (min(ys) + max(ys)) / 2 == pytest.approx(148.5, abs=0.01)
    assert max(xs) - min(xs) == pytest.approx((x1 - x0) * 20, abs=0.01)
    assert max(ys) - min(ys) == pytest.approx((y1 - y0) * 20, abs=0.01)


def test_drawing_that_does_not_fit(house: api.Project) -> None:
    with pytest.raises(api.DrawingError, match=r"at 1:20 the drawing is .* does not fit on A4"):
        api.plan_svg(house, "Piano terra", api.Sheet("A4", scale=20))


def test_bad_sheet() -> None:
    p = api.new_project("P")
    api.add_level(p, "G", 0.0)
    with pytest.raises(api.DrawingError, match="unknown paper size"):
        api.plan_svg(p, "G", api.Sheet("B5"))
    with pytest.raises(api.DrawingError, match="positive"):
        api.plan_svg(p, "G", api.Sheet(scale=0))


def test_empty_level_gives_an_empty_sheet() -> None:
    p = api.new_project("P")
    api.add_level(p, "G", 0.0)
    svg = ET.fromstring(api.plan_svg(p, "G"))
    assert list(svg.iter(f"{SVG}path")) == []
    assert [t.text for t in svg.iter(f"{SVG}text")] == ["P - G - 1:50"]


def test_title_is_escaped() -> None:
    p = api.new_project("A & B <test>")
    api.add_level(p, "G", 0.0)
    svg = ET.fromstring(api.plan_svg(p, "G"))  # would not parse if unescaped
    assert next(svg.iter(f"{SVG}title")).text == "A & B <test> - G - 1:50"


# ----------------------------------------------------------- determinism


def test_output_is_deterministic(house: api.Project, tmp_path: Path) -> None:
    first = api.plan_svg(house, "Piano terra")
    assert api.plan_svg(house, "Piano terra") == first
    api.save(house, tmp_path / "h.bbim")
    assert api.plan_svg(api.load(tmp_path / "h.bbim"), "Piano terra") == first
    assert "-0 " not in first and '-0"' not in first


@pytest.mark.parametrize(
    ("name", "level", "sheet"),
    [
        ("plan-ground-a3-50", "Piano terra", api.Sheet("A3", False, 50)),
        ("plan-ground-a4-100-portrait", "Piano terra", api.Sheet("A4", True, 100)),
        ("plan-first-a4-100", "Primo piano", api.Sheet("A4", False, 100)),
    ],
)
def test_golden(
    house: api.Project, update_golden: bool, name: str, level: str, sheet: api.Sheet
) -> None:
    path = GOLDEN / f"{name}.svg"
    text = api.plan_svg(house, level, sheet)
    if update_golden:
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    assert path.exists(), f"{path.name} is missing; run pytest --update-golden"
    assert text == path.read_text(encoding="utf-8"), (
        f"{path.name} changed; look at the new output and, if it is right, "
        "run pytest --update-golden"
    )


# -------------------------------------------------------------------- CLI


def test_plan_command(
    house: api.Project, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "h.bbim"
    api.save(house, project)
    out = tmp_path / "plan.svg"
    args = ["plan", str(project), "piano terra", str(out), "--scale", "1:100", "--paper", "A4"]
    assert main(args) == 0
    assert "1:100 on A4 landscape" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == api.plan_svg(
        house, "Piano terra", api.Sheet("A4", False, 100)
    )
    assert b"\r\n" not in out.read_bytes()
    assert main(["plan", str(project), "Piano terra", str(out), "--scale", "20"]) == 1
    assert "does not fit" in capsys.readouterr().err
    assert main(["plan", str(project), "Piano terra", str(out), "--cut", "2,2"]) == 0
