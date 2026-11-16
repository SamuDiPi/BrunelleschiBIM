"""The 3D view in the window (M12). On Qt's offscreen platform there is no OpenGL, so
these tests cover everything but the drawing: scene, camera, picking, synchronisation.
The drawing itself is tested in ``test_render3d.py`` in a separate process."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from brunelleschi import api
from brunelleschi.gui.document import Document
from brunelleschi.gui.main_window import MainWindow


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    p = api.new_project("Casa")
    g = api.add_level(p, "Piano terra", 0.0)
    f = api.add_level(p, "Primo piano", 3.0)
    c = [(0, 0), (6, 0), (6, 4), (0, 4)]
    w = [api.add_wall(p, s, c[(i + 1) % 4], 0.3, g.id, top_level=f.id) for i, s in enumerate(c)]
    api.add_door(p, w[0].id, 1.5, 0.9, 2.1)
    api.add_window(p, w[2].id, 3.0, 1.2, 1.4, 0.9)
    path = tmp_path / "casa.bbim"
    api.save(p, path)
    win = MainWindow(Document())
    win.confirm_discard = lambda: True  # type: ignore[method-assign]
    qtbot.addWidget(win)
    win.resize(1400, 800)
    win.show()
    assert win.open_file(path)
    return win


def screen_point(win: MainWindow, point: list[float]) -> QPoint:
    v = win.viewport
    clip = v.camera.matrix(v.width(), v.height()) @ np.array([*point, 1.0])
    ndc = clip[:3] / clip[3]
    return QPoint(int((ndc[0] + 1) / 2 * v.width()), int((1 - ndc[1]) / 2 * v.height()))


def test_scene_follows_the_model(window: MainWindow) -> None:
    v = window.viewport
    assert len(v.scene.elements) == 6
    assert v.scene.bounds()[1][2] == pytest.approx(3.0)  # type: ignore[index]
    revision = v.revision
    window.document.select(window.document.project.levels[1].id)
    field = window.properties.fields["elevation"]
    field.setText("3,40")  # type: ignore[union-attr]
    field.editingFinished.emit()  # type: ignore[union-attr]
    assert v.revision > revision
    assert v.scene.bounds()[1][2] == pytest.approx(3.4)  # type: ignore[index]
    window.undo_action.trigger()
    assert v.scene.bounds()[1][2] == pytest.approx(3.0)  # type: ignore[index]


def test_clicking_in_3d_selects(window: MainWindow) -> None:
    v = window.viewport
    v.fit()
    # The middle of the south wall's outer face, above the door: seen from the
    # south-west, it faces the camera.
    target = screen_point(window, [4.5, -0.15, 1.5])
    QTest.mouseClick(v, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target)
    assert window.document.selected == window.document.project.walls[0].id
    assert window.properties.heading.text().startswith("Wall ")
    QTest.mouseClick(v, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(5, 5))
    assert window.document.selected is None  # empty sky


def test_door_is_picked_before_the_wall_behind(window: MainWindow) -> None:
    window.viewport.fit()
    door = window.document.project.doors[0]
    target = screen_point(window, [1.5, -0.02, 1.0])  # just in front of the leaf's centre
    assert window.viewport.pick_at(target.x(), target.y()) == door.id


def test_drag_orbits_and_does_not_select(window: MainWindow) -> None:
    v = window.viewport
    yaw = v.camera.yaw
    a, b = QPoint(300, 300), QPoint(360, 300)
    QTest.mousePress(v, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a)
    QTest.mouseMove(v, b)
    QTest.mouseRelease(v, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, b)
    assert v.camera.yaw != yaw
    assert window.document.selected is None


def test_3d_view_can_be_hidden(window: MainWindow) -> None:
    window.show_3d_action.trigger()
    assert not window.view_3d.isVisible()
    window.show_3d_action.trigger()
    assert window.view_3d.isVisible()


def test_without_opengl_the_panel_says_why(window: MainWindow) -> None:
    from brunelleschi.gui.renderer import gl_unavailable_reason

    reason = gl_unavailable_reason()
    if reason is None:
        assert window.view_3d is window.viewport
    else:  # Qt's offscreen platform, used by the tests on Windows
        assert window.view_3d is not window.viewport
        assert "3D view unavailable" in window.view_3d.text()  # type: ignore[attr-defined]


def test_editing_in_plan_updates_3d(window: MainWindow) -> None:
    p = window.document.project
    window.document.edit(lambda: api.add_wall(p, (3, 0), (3, 4), 0.12, "Piano terra", height=2.0))
    assert len(window.viewport.scene.elements) == 7
    window.undo()
    assert len(window.viewport.scene.elements) == 6
