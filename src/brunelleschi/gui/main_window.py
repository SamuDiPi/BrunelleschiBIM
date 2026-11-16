"""The main window: plan in the centre, project browser and properties at the side."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QToolBar,
)

from brunelleschi import api
from brunelleschi.gui.browser import ProjectBrowser
from brunelleschi.gui.document import Document
from brunelleschi.gui.plan_view import PlanView
from brunelleschi.gui.properties import PropertiesPanel

FILE_FILTER = "BrunelleschiBIM project (*.bbim)"


class MainWindow(QMainWindow):
    def __init__(self, document: Document | None = None) -> None:
        super().__init__()
        self.document = document or Document()
        self.plan = PlanView(self.document)
        self.browser = ProjectBrowser(self.document)
        self.properties = PropertiesPanel(self.document)
        self.setCentralWidget(self.plan)
        self._dock("Project", self.browser, Qt.DockWidgetArea.LeftDockWidgetArea)
        self._dock("Properties", self.properties, Qt.DockWidgetArea.RightDockWidgetArea)
        self.status = QLabel()  # messages: what happened, what was refused and why
        self.coords = QLabel()  # cursor position, snap and tool hint
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addPermanentWidget(self.coords)
        self._actions()
        self._toolbar()
        self.document.changed.connect(self._update_state)
        self.document.error.connect(self.show_error)
        self.resize(1280, 800)
        self._update_state()

    # ------------------------------------------------------------ layout

    def _dock(self, title: str, widget: object, area: Qt.DockWidgetArea) -> None:
        dock = QDockWidget(title, self)
        dock.setObjectName(title)
        dock.setWidget(widget)  # type: ignore[arg-type]
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(area, dock)

    def _action(
        self,
        text: str,
        slot: object,
        shortcut: QKeySequence | QKeySequence.StandardKey | str | None = None,
    ) -> QAction:
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        return action

    def _actions(self) -> None:
        std = QKeySequence.StandardKey
        self.new_action = self._action("&New", self.new_file, std.New)
        self.open_action = self._action("&Open...", self.open_dialog, std.Open)
        self.save_action = self._action("&Save", self.save, std.Save)
        self.save_as_action = self._action("Save &As...", self.save_as_dialog, std.SaveAs)
        self.quit_action = self._action("&Quit", self.close, std.Quit)
        self.undo_action = self._action("&Undo", self.undo, std.Undo)
        self.redo_action = self._action("&Redo", self.redo, std.Redo)
        self.fit_action = self._action("&Fit plan", self.plan.fit, "F")
        self.delete_action = self._action("&Delete", self.delete_selected, std.Delete)
        self.add_level_action = self._action("Add &level", self.add_level)
        self.ortho_action = self._action("&Ortho", self._toggle_ortho, "F8")
        self.ortho_action.setCheckable(True)
        self.tool_actions: dict[str, QAction] = {}
        group = QActionGroup(self)
        for name, text, key in (
            ("select", "&Select", "S"),
            ("wall", "&Wall", "W"),
            ("door", "&Door", "D"),
            ("window", "Wi&ndow", "N"),
        ):
            action = self._action(text, lambda _=False, n=name: self.plan.set_tool(n), key)
            action.setCheckable(True)
            group.addAction(action)
            self.tool_actions[name] = action
        self.tool_actions["select"].setChecked(True)
        self.plan.tool_changed.connect(lambda n: self.tool_actions[n].setChecked(True))
        self.plan.status_changed.connect(self.coords.setText)

        file_menu = self.menuBar().addMenu("&File")
        for a in (self.new_action, self.open_action, self.save_action, self.save_as_action):
            file_menu.addAction(a)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)
        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.add_level_action)
        edit_menu.addAction(self.delete_action)
        draw_menu = self.menuBar().addMenu("&Draw")
        for action in self.tool_actions.values():
            draw_menu.addAction(action)
        draw_menu.addSeparator()
        draw_menu.addAction(self.ortho_action)
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.fit_action)

    def _toolbar(self) -> None:
        bar = QToolBar("Main")
        bar.setObjectName("Main")
        bar.setMovable(False)
        for a in (self.open_action, self.save_action, self.undo_action, self.redo_action):
            bar.addAction(a)
        bar.addSeparator()
        bar.addWidget(QLabel(" Level: "))
        self.level_combo = QComboBox()
        self.level_combo.setMinimumWidth(180)
        self.level_combo.currentIndexChanged.connect(self._level_chosen)
        bar.addWidget(self.level_combo)
        bar.addAction(self.fit_action)
        bar.addSeparator()
        for action in self.tool_actions.values():
            bar.addAction(action)
        bar.addAction(self.ortho_action)
        bar.addWidget(QLabel(" Thickness: "))
        self.thickness_edit = QLineEdit("0.30")
        self.thickness_edit.setMaximumWidth(60)
        self.thickness_edit.editingFinished.connect(self._thickness_changed)
        bar.addWidget(self.thickness_edit)
        self.addToolBar(bar)

    # ------------------------------------------------------------- state

    def _update_state(self) -> None:
        self.setWindowTitle(self.document.title())
        project = self.document.project
        undo, redo = api.undo_label(project), api.redo_label(project)
        self.undo_action.setEnabled(undo is not None)
        self.redo_action.setEnabled(redo is not None)
        self.undo_action.setText(f"&Undo {undo}" if undo else "&Undo")
        self.redo_action.setText(f"&Redo {redo}" if redo else "&Redo")
        self._fill_levels()

    def _fill_levels(self) -> None:
        combo = self.level_combo
        combo.blockSignals(True)
        combo.clear()
        for lv in reversed(self.document.project.levels_by_elevation()):
            combo.addItem(f"{lv.name}  ({lv.elevation:+.2f} m)", str(lv.id))
        index = combo.findData(str(self.plan.level_id)) if self.plan.level_id else -1
        combo.setCurrentIndex(index if index >= 0 else combo.count() - 1)
        combo.blockSignals(False)
        if index < 0 and combo.count():
            self._level_chosen()

    def _level_chosen(self) -> None:
        value = self.level_combo.currentData()
        self.plan.set_level(UUID(value) if value else None)

    def _toggle_ortho(self) -> None:
        self.plan.ortho = self.ortho_action.isChecked()

    def _thickness_changed(self) -> None:
        try:
            value = float(self.thickness_edit.text().strip().replace(",", "."))
        except ValueError:
            value = -1.0
        if 0 < value <= 5:
            self.plan.wall_thickness = value
            self.thickness_edit.setText(f"{value:.2f}")
        else:
            self.show_error(f"not a wall thickness: {self.thickness_edit.text()!r}")
            self.thickness_edit.setText(f"{self.plan.wall_thickness:.2f}")

    def add_level(self) -> None:
        """A new level 3 m above the highest one, named after its position."""
        p = self.document.project
        levels = p.levels_by_elevation()
        elevation = levels[-1].elevation + 3.0 if levels else 0.0
        names = {lv.name.casefold() for lv in levels}
        number = len(levels)
        while f"level {number}" in names:
            number += 1
        if self.document.edit(lambda: api.add_level(p, f"Level {number}", elevation)):
            self.document.select(p.levels[-1].id)

    def delete_selected(self) -> None:
        selected = self.document.selected
        if selected is None:
            self.show_error("nothing selected")
            return
        kind = self.document.kind_of(selected)
        p = self.document.project
        if kind == "level":
            self.document.edit(lambda: api.delete_level(p, selected))
        elif kind == "wall":
            self.document.edit(lambda: api.delete_wall(p, selected))
        elif kind in ("door", "window"):
            self.document.edit(lambda: api.delete_hosted(p, selected))

    def show_error(self, message: str) -> None:
        self.status.setText(message)

    # ------------------------------------------------------------- edits

    def undo(self) -> None:
        label = self.document.undo()
        self.status.setText(f"Undone: {label}" if label else "Nothing to undo")

    def redo(self) -> None:
        label = self.document.redo()
        self.status.setText(f"Redone: {label}" if label else "Nothing to redo")

    # ------------------------------------------------------------- files

    def confirm_discard(self) -> bool:
        """Ask before losing unsaved changes. Tests replace this method."""
        if not self.document.modified:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "The project has unsaved changes. Discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Discard

    def new_file(self) -> None:
        if self.confirm_discard():
            self.document.new()

    def open_file(self, path: Path) -> bool:
        if not self.confirm_discard():
            return False
        try:
            self.document.open(path)
        except api.BrunelleschiError as exc:
            self.show_error(f"Cannot open {path.name}: {exc}")
            return False
        self.plan.fit()
        self.status.setText(f"Opened {path}")
        return True

    def open_dialog(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, "Open project", "", FILE_FILTER)
        if name:
            self.open_file(Path(name))

    def save(self) -> bool:
        if self.document.path is None:
            return self.save_as_dialog()
        return self.save_to(self.document.path)

    def save_to(self, path: Path) -> bool:
        try:
            self.document.save(path)
        except (api.BrunelleschiError, OSError) as exc:
            self.show_error(f"Cannot save {path.name}: {exc}")
            return False
        self.status.setText(f"Saved {path}")
        return True

    def save_as_dialog(self) -> bool:
        name, _ = QFileDialog.getSaveFileName(self, "Save project", "", FILE_FILTER)
        return self.save_to(Path(name)) if name else False

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.confirm_discard():
            event.accept()
        else:
            event.ignore()
