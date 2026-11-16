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
    QSplitter,
    QToolBar,
    QWidget,
)

from brunelleschi import api
from brunelleschi.gui.browser import ProjectBrowser
from brunelleschi.gui.document import Document
from brunelleschi.gui.plan_view import PlanView
from brunelleschi.gui.properties import PropertiesPanel
from brunelleschi.gui.renderer import gl_unavailable_reason
from brunelleschi.gui.viewport import Viewport3D

FILE_FILTER = "BrunelleschiBIM project (*.bbim)"


class MainWindow(QMainWindow):
    def __init__(self, document: Document | None = None) -> None:
        super().__init__()
        self.document = document or Document()
        self.plan = PlanView(self.document)
        self.browser = ProjectBrowser(self.document)
        self.properties = PropertiesPanel(self.document)
        self.viewport = Viewport3D(self.document)
        # Where OpenGL 3.3 is missing (old drivers, virtual machines), say so instead of
        # showing an empty panel. The viewport object still follows the model.
        reason = gl_unavailable_reason()
        if reason is None:
            self.view_3d: QWidget = self.viewport
        else:
            self.viewport.unavailable = reason
            label = QLabel(f"3D view unavailable: {reason}.\nThe plan and everything else work.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            self.view_3d = label
        self.views = QSplitter(Qt.Orientation.Horizontal)
        self.views.addWidget(self.plan)
        self.views.addWidget(self.view_3d)
        self.views.setSizes([1, 1])
        self.setCentralWidget(self.views)
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
        self.export_ifc_action = self._action("Export &IFC...", self.export_ifc_dialog)
        self.export_plan_action = self._action("Export &plan as SVG...", self.export_plan_dialog)
        self.quit_action = self._action("&Quit", self.close, std.Quit)
        self.undo_action = self._action("&Undo", self.undo, std.Undo)
        self.redo_action = self._action("&Redo", self.redo, std.Redo)
        self.fit_action = self._action("&Fit plan", self.plan.fit, "F")
        self.fit_3d_action = self._action("Fit &3D", self.viewport.fit, "Shift+F")
        self.show_3d_action = self._action("3D &view", self._toggle_3d, "F3")
        self.show_3d_action.setCheckable(True)
        self.show_3d_action.setChecked(True)
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
        file_menu.addAction(self.export_ifc_action)
        file_menu.addAction(self.export_plan_action)
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
        view_menu.addAction(self.fit_3d_action)
        view_menu.addAction(self.show_3d_action)

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

    def _toggle_3d(self) -> None:
        self.view_3d.setVisible(self.show_3d_action.isChecked())

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

    # ----------------------------------------------------------- export

    def _default_name(self, suffix: str) -> str:
        path = self.document.path
        return str(path.with_suffix(suffix)) if path else f"{self.document.project.name}{suffix}"

    def export_ifc_to(self, path: Path) -> bool:
        from brunelleschi.ifc import write_ifc  # IfcOpenShell loads only when needed

        try:
            write_ifc(self.document.project, path)
        except (api.BrunelleschiError, OSError) as exc:
            self.show_error(f"Cannot export {path.name}: {exc}")
            return False
        self.status.setText(f"Exported IFC4 to {path}")
        return True

    def export_ifc_dialog(self) -> None:
        name, _ = QFileDialog.getSaveFileName(
            self, "Export IFC", self._default_name(".ifc"), "IFC4 (*.ifc)"
        )
        if name:
            self.export_ifc_to(Path(name))

    def export_plan_to(self, path: Path) -> bool:
        """The plan of the level shown, on A3 at the first scale it fits: 1:50, 1:100, 1:200."""
        level_id = self.plan.level_id
        if level_id is None:
            self.show_error("there is no level to draw")
            return False
        project = self.document.project
        for scale in (50.0, 100.0, 200.0):
            try:
                api.write_plan_svg(project, level_id, path, api.Sheet("A3", scale=scale))
            except api.DrawingError:
                continue
            except OSError as exc:
                self.show_error(f"Cannot export {path.name}: {exc}")
                return False
            level = project.level(level_id).name
            self.status.setText(f"Exported the plan of {level!r} at 1:{scale:g} on A3 to {path}")
            return True
        self.show_error("the plan does not fit on A3 even at 1:200; use bbim plan for larger paper")
        return False

    def export_plan_dialog(self) -> None:
        name, _ = QFileDialog.getSaveFileName(
            self, "Export plan", self._default_name(".svg"), "SVG drawing (*.svg)"
        )
        if name:
            self.export_plan_to(Path(name))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.confirm_discard():
            event.accept()
        else:
            event.ignore()
