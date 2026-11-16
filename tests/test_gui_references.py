"""Linked IFC files in the window (M13), with pytest-qt on the offscreen platform."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from brunelleschi import api
from brunelleschi.gui.document import Document
from brunelleschi.gui.main_window import MainWindow
from foreign_ifc import build_foreign_ifc


@pytest.fixture
def folders(tmp_path: Path) -> tuple[Path, Path]:
    """A project in proj/ and an IFC of others in ext/, side by side."""
    project_dir, ext_dir = tmp_path / "proj", tmp_path / "ext"
    project_dir.mkdir()
    ext_dir.mkdir()
    p = api.new_project("Casa")
    api.add_level(p, "Piano terra", 0.0)
    api.add_level(p, "Primo piano", 3.0)
    api.save(p, project_dir / "casa.bbim")
    build_foreign_ifc(ext_dir / "strutture.ifc")
    return project_dir, ext_dir


@pytest.fixture
def window(qtbot: QtBot, folders: tuple[Path, Path]) -> MainWindow:
    win = MainWindow(Document())
    win.confirm_discard = lambda: True  # type: ignore[method-assign]
    qtbot.addWidget(win)
    win.resize(1400, 800)
    win.show()
    assert win.open_file(folders[0] / "casa.bbim")
    return win


def link(qtbot: QtBot, win: MainWindow, path: Path) -> None:
    with qtbot.waitSignal(win.references.loaded, timeout=60000):
        assert win.link_ifc(path)


def reference_item_text(win: MainWindow) -> str:
    item = win.browser.item_for(win.document.project.references[0].id)
    assert item is not None
    return item.text(0)


def test_link_loads_in_the_background_and_shows_everywhere(
    qtbot: QtBot, window: MainWindow, folders: tuple[Path, Path]
) -> None:
    link(qtbot, window, folders[1] / "strutture.ifc")
    (reference,) = window.document.project.references
    assert reference.path == "../ext/strutture.ifc"  # relative: the project stays movable
    assert reference.name == "strutture"
    assert "4 elements, 1 without geometry" in reference_item_text(window)
    assert window.status.text() == "strutture: 4 elements, 1 without geometry"
    # Plan of the ground floor: walls and column of the reference are cut at 1.20 m.
    ground = window.document.project.level("Piano terra")
    assert len(window.references.plan_lines(ground.id, 1.2)) == 3
    # 3D: the reference elements are in the scene, labelled, not selectable.
    labels = [e for e in window.viewport.scene.elements if isinstance(e, str)]
    assert sorted(labels) == [
        "strutture: IfcColumn 'Pilastro'",
        "strutture: IfcSlab 'Solaio'",
        "strutture: IfcWall 'Muro A'",
        "strutture: IfcWall 'Muro B'",
    ]
    # Properties: the storey matches.
    window.document.select(reference.id)
    assert window.properties.heading.text() == "Linked IFC: strutture"


def test_link_is_undoable_and_deletable(
    qtbot: QtBot, window: MainWindow, folders: tuple[Path, Path]
) -> None:
    link(qtbot, window, folders[1] / "strutture.ifc")
    assert window.undo_action.text() == "&Undo Link IFC 'strutture'"
    window.undo_action.trigger()
    assert window.document.project.references == []
    ground = window.document.project.level("Piano terra")
    assert window.references.plan_lines(ground.id, 1.2) == []
    with qtbot.waitSignal(window.references.loaded, timeout=60000):
        window.redo_action.trigger()
    window.document.select(window.document.project.references[0].id)
    window.delete_action.trigger()
    assert window.document.project.references == []
    assert not [e for e in window.viewport.scene.elements if isinstance(e, str)]


def test_saved_link_reloads_after_moving_the_folders(
    qtbot: QtBot, window: MainWindow, folders: tuple[Path, Path], tmp_path: Path
) -> None:
    link(qtbot, window, folders[1] / "strutture.ifc")
    assert window.save()
    moved = tmp_path / "moved"
    moved.mkdir()
    shutil.copytree(folders[0], moved / "proj")
    shutil.copytree(folders[1], moved / "ext")
    with qtbot.waitSignal(window.references.loaded, timeout=60000):
        assert window.open_file(moved / "proj" / "casa.bbim")
    assert "4 elements" in reference_item_text(window)


def test_a_missing_file_is_reported(
    qtbot: QtBot, window: MainWindow, folders: tuple[Path, Path]
) -> None:
    p = window.document.project
    with qtbot.waitSignal(window.references.loaded, timeout=60000):
        window.document.edit(lambda: api.add_reference(p, "../ext/nowhere.ifc"))
    assert "file not found" in reference_item_text(window)
    assert window.link_ifc(folders[1] / "nowhere-either.ifc") is False
    assert window.status.text().startswith("file not found")
