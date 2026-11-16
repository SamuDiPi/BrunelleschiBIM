"""The main window (M10), driven with pytest-qt on Qt's offscreen platform."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QComboBox, QLineEdit
from pytestqt.qtbot import QtBot

from brunelleschi import api
from brunelleschi.gui.app import main, parse_args
from brunelleschi.gui.document import Document
from brunelleschi.gui.main_window import MainWindow


@pytest.fixture
def house_file(tmp_path: Path) -> Path:
    """The M7 house: two levels, four walls with mitred corners, a door and a window."""
    p = api.new_project("Casa")
    g = api.add_level(p, "Piano terra", 0.0)
    f = api.add_level(p, "Primo piano", 3.0)
    c = [(0, 0), (6, 0), (6, 4), (0, 4)]
    w = [api.add_wall(p, s, c[(i + 1) % 4], 0.3, g.id, top_level=f.id) for i, s in enumerate(c)]
    api.add_door(p, w[0].id, 1.5, 0.9, 2.1)
    api.add_window(p, w[2].id, 3.0, 1.2, 1.4, 0.9)
    path = tmp_path / "casa.bbim"
    api.save(p, path)
    return path


@pytest.fixture
def window(qtbot: QtBot, house_file: Path) -> MainWindow:
    win = MainWindow(Document())
    win.confirm_discard = lambda: True  # type: ignore[method-assign]
    qtbot.addWidget(win)
    win.resize(1280, 800)
    assert win.open_file(house_file)
    return win


def field(win: MainWindow, name: str) -> QLineEdit:
    widget = win.properties.fields[name]
    assert isinstance(widget, QLineEdit)
    return widget


def combo(win: MainWindow, name: str) -> QComboBox:
    widget = win.properties.fields[name]
    assert isinstance(widget, QComboBox)
    return widget


def type_into(edit: QLineEdit, text: str) -> None:
    edit.setText(text)
    edit.editingFinished.emit()


def select(win: MainWindow, kind: str, index: int = 0) -> None:
    p = win.document.project
    stores: dict[str, list[api.Level] | list[api.Wall] | list[api.Door] | list[api.Window]] = {
        "level": p.levels,
        "wall": p.walls,
        "door": p.doors,
        "window": p.windows,
    }
    win.document.select(stores[kind][index].id)


def browser_groups(win: MainWindow) -> list[str]:
    items = (win.browser.topLevelItem(i) for i in range(win.browser.topLevelItemCount()))
    return [item.text(0) for item in items if item is not None]


# ---------------------------------------------------------------- opening


def test_opens_the_house(window: MainWindow, house_file: Path) -> None:
    assert window.windowTitle().startswith("casa.bbim - Casa")
    assert browser_groups(window) == [
        "Levels (2)",
        "Walls (4)",
        "Doors (1)",
        "Windows (1)",
        "References (0)",
    ]
    assert window.level_combo.count() == 2
    assert window.level_combo.currentText().startswith("Piano terra")
    layers = {p.layer for p in window.plan.drawing.flat()}
    assert {"wall-cut", "door", "door-swing", "window"} <= layers
    assert not window.undo_action.isEnabled()


def test_opening_a_bad_file_reports_and_keeps_the_project(
    window: MainWindow, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.bbim"
    bad.write_text("not json", encoding="utf-8")
    assert not window.open_file(bad)
    assert "Cannot open bad.bbim" in window.status.text()
    assert len(window.document.project.walls) == 4


def test_selection_is_shared(window: MainWindow) -> None:
    select(window, "wall", 1)
    wall = window.document.project.walls[1]
    assert window.browser.selectedItems()[0].text(0).startswith(f"Wall {api.short_id(wall.id)}")
    assert window.properties.heading.text() == f"Wall {api.short_id(wall.id)}"
    window.browser.clearSelection()
    window.browser.item_for(window.document.project.doors[0].id).setSelected(True)  # type: ignore[union-attr]
    assert window.document.selected == window.document.project.doors[0].id
    assert window.properties.heading.text().startswith("Door ")


# ------------------------------------------------------- the M10 criterion


def test_level_elevation_edit_updates_plan_and_undoes(window: MainWindow) -> None:
    select(window, "level", 1)  # Primo piano
    level = window.document.project.level("Primo piano")
    revision = window.plan.revision
    type_into(field(window, "elevation"), "3,40")  # decimal comma
    assert level.elevation == 3.4
    assert window.plan.revision > revision  # the plan was regenerated
    wall = window.document.project.walls[0]
    assert window.document.project.wall_z_range(wall)[1] == pytest.approx(3.4)
    assert window.undo_action.text() == "&Undo Change level elevation"
    assert "*" in window.windowTitle()
    window.undo_action.trigger()
    assert level.elevation == 3.0
    assert field(window, "elevation").text() == "3.000"
    assert "*" not in window.windowTitle()  # back to the saved state
    window.redo_action.trigger()
    assert level.elevation == 3.4


def test_refused_value_is_explained_and_reset(window: MainWindow) -> None:
    select(window, "level", 1)
    type_into(field(window, "elevation"), "-1")  # the walls would end below their base
    assert window.document.project.level("Primo piano").elevation == 3.0
    assert field(window, "elevation").text() == "3.000"
    assert "must be above base" in window.properties.message.text()
    assert "must be above base" in window.status.text()
    assert not window.undo_action.isEnabled()
    type_into(field(window, "elevation"), "three")
    assert "not a number of metres" in window.properties.message.text()


def test_wall_thickness_changes_the_plan(window: MainWindow) -> None:
    def cut_area() -> float:
        return sum(
            s.area for s in api.wall_geometry(window.document.project).plan_cut(1.2).values()
        )

    select(window, "wall", 0)
    before = cut_area()
    type_into(field(window, "thickness"), "0.5")
    assert cut_area() > before
    assert window.document.project.walls[0].thickness == 0.5
    window.undo()
    assert cut_area() == pytest.approx(before)


def test_wall_top_mode_switch(window: MainWindow) -> None:
    select(window, "wall", 0)
    assert not field(window, "height").isEnabled()
    top = combo(window, "top_mode")
    top.setCurrentIndex(top.findData("height"))
    wall = window.document.project.walls[0]
    assert wall.top == api.UnconnectedHeight(3.0)
    assert field(window, "height").isEnabled()
    assert not combo(window, "top_level").isEnabled()
    type_into(field(window, "height"), "2.5")
    assert window.document.project.wall_z_range(wall)[1] == 2.5
    window.undo()
    window.undo()
    assert isinstance(window.document.project.wall(wall.id).top, api.TopAtLevel)


def test_door_parameters(window: MainWindow) -> None:
    select(window, "door")
    door = window.document.project.doors[0]
    swing = combo(window, "swing_side")
    swing.setCurrentIndex(swing.findData("right"))
    assert door.swing_side == api.Side.RIGHT
    type_into(field(window, "width"), "1,00")
    assert door.width == 1.0
    type_into(field(window, "position"), "5.9")  # would stick out of the wall
    assert door.position == 1.5
    assert "does not fit" in window.properties.message.text()


def test_deleting_the_selected_element_by_undo_clears_the_panel(window: MainWindow) -> None:
    p = window.document.project
    window.document.edit(lambda: api.add_wall(p, (0, 6), (6, 6), 0.2, "Piano terra", height=2))
    select(window, "wall", 4)
    window.undo()  # removes the selected wall
    assert window.document.selected is None
    assert window.properties.heading.text() == "No selection"


def test_level_switch_changes_the_plan(window: MainWindow) -> None:
    window.level_combo.setCurrentIndex(0)  # highest first: Primo piano
    assert window.plan.level_id == window.document.project.level("Primo piano").id
    assert not [p for p in window.plan.drawing.flat() if p.layer == "wall-cut"]


# ------------------------------------------------------------------ files


def test_save_clears_the_modified_mark(window: MainWindow, house_file: Path) -> None:
    select(window, "level", 0)
    type_into(field(window, "name"), "Terra")
    assert "*" in window.windowTitle()
    assert window.save()
    assert "*" not in window.windowTitle()
    assert api.load(house_file).level("Terra").elevation == 0.0


def test_new_project(window: MainWindow) -> None:
    window.new_file()
    assert window.windowTitle().startswith("untitled - Untitled")
    assert browser_groups(window) == [
        "Levels (1)",
        "Walls (0)",
        "Doors (0)",
        "Windows (0)",
        "References (0)",
    ]


def test_window_can_be_captured(window: MainWindow, tmp_path: Path) -> None:
    window.show()
    image = window.grab()
    assert (image.width(), image.height()) == (1280, 800)
    assert image.save(str(tmp_path / "window.png"))


# ------------------------------------------------------------- start-up


@pytest.mark.parametrize(
    ("argv", "expected"),
    [([], None), (["casa.bbim"], Path("casa.bbim")), (["CASA.BBIM"], Path("CASA.BBIM"))],
)
def test_arguments_accepted(argv: list[str], expected: Path | None) -> None:
    assert parse_args(argv) == expected


@pytest.mark.parametrize("argv", [["bootstrap.py"], ["-m", "x"], ["a.bbim", "b.bbim"], ["--x"]])
def test_unexpected_arguments_are_refused_without_a_window(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == 2
    assert "unexpected arguments" in capsys.readouterr().err


# ----------------------------------------------------------------- export


def test_export_ifc(window: MainWindow, tmp_path: Path) -> None:
    from brunelleschi.ifc import validate_ifc

    out = tmp_path / "casa.ifc"
    assert window.export_ifc_to(out)
    assert "Exported IFC4" in window.status.text()
    assert validate_ifc(out).issues == ()


def test_export_plan_picks_a_scale_that_fits(window: MainWindow, tmp_path: Path) -> None:
    out = tmp_path / "plan.svg"
    assert window.export_plan_to(out)
    assert "at 1:50 on A3" in window.status.text()
    assert out.read_text(encoding="utf-8") == api.plan_svg(
        window.document.project, "Piano terra", api.Sheet("A3", scale=50)
    )
    p = window.document.project
    window.document.edit(lambda: api.add_wall(p, (0, 0), (30, 0), 0.3, "Piano terra", height=3))
    assert window.export_plan_to(out)
    assert "at 1:100 on A3" in window.status.text()


def test_export_to_a_bad_place(window: MainWindow, tmp_path: Path) -> None:
    assert not window.export_ifc_to(tmp_path / "no-such-folder" / "x.ifc")
    assert "Cannot export x.ifc" in window.status.text()
    assert not (tmp_path / "no-such-folder").exists()  # no folder created behind our back
    assert not window.export_plan_to(tmp_path / "no-such-folder" / "x.svg")


def test_plan_keeps_fitting_until_the_user_navigates(window: MainWindow, qtbot: QtBot) -> None:
    window.show()  # offscreen: laid out in memory only
    window.resize(700, 450)
    qtbot.wait(10)
    small = window.plan.scale
    window.resize(1600, 1000)
    qtbot.wait(10)
    assert window.plan.scale > small  # refitted to the larger view
    window.plan.set_view((0.0, 0.0), 10.0)  # as if the user had zoomed
    window.resize(900, 600)
    qtbot.wait(10)
    assert window.plan.scale == 10.0


def test_export_dxf(window: MainWindow, tmp_path: Path) -> None:
    from ezdxf.filemanagement import readfile

    out = tmp_path / "pianta.dxf"
    assert window.export_dxf_to(out)
    assert "as DXF (millimetres)" in window.status.text()
    doc = readfile(out)
    assert {e.dxf.name for e in doc.modelspace().query("INSERT")} == {
        "DOOR_900",
        "WINDOW_1200x300",
    }
    assert not window.export_dxf_to(tmp_path / "missing" / "x.dxf")
