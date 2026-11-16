"""Editing in the plan with the mouse (M11), driven with pytest-qt on the offscreen
platform: the M7 house is rebuilt with clicks only, then every step is undone."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from brunelleschi import api
from brunelleschi.gui.document import Document
from brunelleschi.gui.main_window import MainWindow
from brunelleschi.ifc import export_ifc, validate_ifc

SCALE = 60.0  # pixels per metre: grid points fall on whole pixels with this view
CENTRE = (3.0, 2.0)


@pytest.fixture
def window(qtbot: QtBot) -> MainWindow:
    win = MainWindow(Document())
    win.confirm_discard = lambda: True  # type: ignore[method-assign]
    qtbot.addWidget(win)
    win.resize(1280, 800)
    win.show()  # offscreen: laid out in memory only
    win.plan.set_view(CENTRE, SCALE)
    return win


def at(win: MainWindow, x: float, y: float) -> QPoint:
    return win.plan.to_screen((x, y)).toPoint()


def click(win: MainWindow, x: float, y: float, shift: bool = False) -> None:
    mod = Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier
    QTest.mouseMove(win.plan, at(win, x, y))
    QTest.mouseClick(win.plan, Qt.MouseButton.LeftButton, mod, at(win, x, y))


def right_click(win: MainWindow) -> None:
    QTest.mouseClick(
        win.plan, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, at(win, 3, 2)
    )


def drag(win: MainWindow, a: tuple[float, float], b: tuple[float, float]) -> None:
    QTest.mousePress(
        win.plan, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(win, *a)
    )
    QTest.mouseMove(win.plan, at(win, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
    QTest.mouseMove(win.plan, at(win, *b))
    QTest.mouseRelease(
        win.plan, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(win, *b)
    )


def build_house_with_the_mouse(win: MainWindow) -> None:
    win.add_level_action.trigger()  # "Level 1" at +3.00 above "Ground floor"
    win.level_combo.setCurrentIndex(win.level_combo.count() - 1)  # back to the ground floor
    win.plan.set_view(CENTRE, SCALE)
    win.tool_actions["wall"].trigger()
    for x, y in [(0, 0), (6, 0), (6, 4), (0, 4), (0.04, 0.03)]:  # the last one snaps to (0, 0)
        click(win, x, y)
    right_click(win)  # ends the chain
    win.tool_actions["door"].trigger()
    click(win, 1.5, 0.1)  # inside the room: the door opens inwards (left of the wall)
    win.tool_actions["window"].trigger()
    click(win, 3.0, 4.05)


def test_rebuild_the_m7_house_with_the_mouse(window: MainWindow) -> None:
    build_house_with_the_mouse(window)
    p = window.document.project
    assert [(w.start, w.end) for w in p.walls] == [
        (api.Point(0, 0), api.Point(6, 0)),
        (api.Point(6, 0), api.Point(6, 4)),
        (api.Point(6, 4), api.Point(0, 4)),
        (api.Point(0, 4), api.Point(0, 0)),
    ]
    first = p.level("Level 1")
    assert all(w.top == api.TopAtLevel(first.id, 0.0) for w in p.walls)
    assert sorted(str(j.kind) for j in api.wall_geometry(p).joins) == ["mitre"] * 4
    (door,) = p.doors
    assert (door.host_id, door.position, door.swing_side) == (p.walls[0].id, 1.5, api.Side.LEFT)
    (window_element,) = p.windows
    assert (window_element.host_id, window_element.position) == (p.walls[2].id, 3.0)
    assert api.wall_geometry(p).issues == ()
    assert validate_ifc(export_ifc(p)).issues == ()


def test_every_step_undoes(window: MainWindow) -> None:
    empty = api.dumps(window.document.project)
    build_house_with_the_mouse(window)
    labels = []
    while window.undo_action.isEnabled():
        labels.append(window.undo_action.text().removeprefix("&Undo "))
        window.undo_action.trigger()
    assert labels == [
        "Add window",
        "Add door",
        "Add wall",
        "Add wall",
        "Add wall",
        "Add wall",
        "Add level 'Level 1'",
    ]
    assert api.dumps(window.document.project) == empty
    while window.redo_action.isEnabled():
        window.redo_action.trigger()
    assert len(window.document.project.walls) == 4


def test_wall_chain_and_cancel(window: MainWindow) -> None:
    window.tool_actions["wall"].trigger()
    click(window, 0, 0)
    QTest.keyClick(window.plan, Qt.Key.Key_Escape)  # cancels the chain, keeps the tool
    click(window, 1, 1)
    click(window, 3, 1)
    assert len(window.document.project.walls) == 1
    assert window.document.project.walls[0].start == api.Point(1, 1)
    QTest.keyClick(window.plan, Qt.Key.Key_Escape)
    QTest.keyClick(window.plan, Qt.Key.Key_Escape)  # nothing in progress: back to select
    assert window.tool_actions["select"].isChecked()


def test_ortho_with_shift(window: MainWindow) -> None:
    window.tool_actions["wall"].trigger()
    click(window, 0, 0)
    click(window, 3, 0.4, shift=True)
    (wall,) = window.document.project.walls
    assert wall.end == api.Point(3, 0)


def test_wall_without_a_level_above_gets_a_height(window: MainWindow) -> None:
    window.thickness_edit.setText("0,20")
    window.thickness_edit.editingFinished.emit()
    window.tool_actions["wall"].trigger()
    click(window, 0, 0)
    click(window, 4, 0)
    (wall,) = window.document.project.walls
    assert wall.top == api.UnconnectedHeight(3.0)
    assert wall.thickness == 0.2


def test_select_and_drag_a_corner(window: MainWindow) -> None:
    build_house_with_the_mouse(window)
    p = window.document.project
    window.tool_actions["select"].trigger()
    click(window, 6.0, 2.0)  # the east wall
    assert window.document.selected == p.walls[1].id
    drag(window, (6, 4), (7, 5))  # its end grip, joined to the north wall
    assert p.walls[1].end == api.Point(7, 5)
    assert p.walls[2].start == api.Point(7, 5)
    assert window.undo_action.text() == "&Undo Move wall end"
    window.undo_action.trigger()
    assert p.walls[2].start == api.Point(6, 4)


def test_drag_a_wall(window: MainWindow) -> None:
    build_house_with_the_mouse(window)
    p = window.document.project
    window.tool_actions["select"].trigger()
    drag(window, (4.0, 4.0), (4.0, 4.5))  # the north wall, half a metre up
    assert (p.walls[2].start, p.walls[2].end) == (api.Point(6, 4.5), api.Point(0, 4.5))
    assert p.walls[1].end == api.Point(6, 4.5)  # neighbours stretch


def test_drag_a_door_along_its_wall(window: MainWindow) -> None:
    build_house_with_the_mouse(window)
    door = window.document.project.doors[0]
    window.tool_actions["select"].trigger()
    drag(window, (1.5, 0.0), (3.2, 0.3))
    assert door.position == 3.2


def test_delete_and_click_away(window: MainWindow) -> None:
    build_house_with_the_mouse(window)
    p = window.document.project
    window.tool_actions["select"].trigger()
    click(window, 0.0, 2.0)
    window.delete_action.trigger()
    assert len(p.walls) == 3
    click(window, 3.0, 2.0)  # empty space
    assert window.document.selected is None
    window.delete_action.trigger()
    assert window.status.text() == "nothing selected"


def test_refused_placement_is_explained(window: MainWindow) -> None:
    window.tool_actions["door"].trigger()
    click(window, 3, 2)
    assert window.status.text() == "click on a wall to place a door"
    window.tool_actions["wall"].trigger()
    click(window, 0, 0)
    click(window, 0.5, 0)
    window.tool_actions["door"].trigger()
    click(window, 0.25, 0)  # a 0.90 m door in a 0.50 m wall
    assert "does not fit" in window.status.text()
    assert window.document.project.doors == []


def test_status_shows_coordinates_and_snap(window: MainWindow) -> None:
    window.tool_actions["wall"].trigger()
    QTest.mouseMove(window.plan, at(window, 2.03, 1.0))
    assert window.coords.text().startswith("x 2.00  y 1.00  [grid]")
    assert "Wall: click the start point" in window.coords.text()
