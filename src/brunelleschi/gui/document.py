"""The open project, as the interface sees it.

Every change goes through ``brunelleschi.api`` commands via ``Document.edit``, so the
interface never mutates the model itself, every change is one undo step, and errors come
back as messages rather than exceptions.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QObject, Signal

from brunelleschi import api


class Document(QObject):
    """A project, the file it belongs to, its selection and whether it has unsaved changes."""

    changed = Signal()  # the model changed: an edit, undo, redo, or another project
    selection_changed = Signal()
    error = Signal(str)  # a change was refused; the message says why

    def __init__(self, project: api.Project | None = None, path: Path | None = None) -> None:
        super().__init__()
        self._project = project or self._untitled()
        self._path = path
        self._selected: UUID | None = None
        self._saved_step: object | None = None
        self._mark_saved()

    # ------------------------------------------------------------- state

    @property
    def project(self) -> api.Project:
        return self._project

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def selected(self) -> UUID | None:
        return self._selected

    @property
    def modified(self) -> bool:
        return self._top_step() is not self._saved_step

    def title(self) -> str:
        name = self._path.name if self._path else "untitled"
        return f"{name}{' *' if self.modified else ''} - {self._project.name} - BrunelleschiBIM"

    # ----------------------------------------------------------- changes

    def edit(self, change: Callable[[], object]) -> bool:
        """Run a change made of API commands. False, and an ``error``, if it was refused."""
        try:
            change()
        except api.BrunelleschiError as exc:
            self.error.emit(str(exc))
            self.changed.emit()  # views show the model's values again
            return False
        self._drop_missing_selection()
        self.changed.emit()
        return True

    def undo(self) -> str | None:
        label = api.undo(self._project)
        if label is not None:
            self._drop_missing_selection()
            self.changed.emit()
        return label

    def redo(self) -> str | None:
        label = api.redo(self._project)
        if label is not None:
            self._drop_missing_selection()
            self.changed.emit()
        return label

    def select(self, element_id: UUID | None) -> None:
        if element_id != self._selected:
            self._selected = element_id
            self.selection_changed.emit()

    # ------------------------------------------------------------- files

    def new(self) -> None:
        self._replace(self._untitled(), None)

    def open(self, path: Path) -> None:
        """Load a project file; raises ``api.ProjectFileError`` if it cannot be read."""
        self._replace(api.load(path), path)

    def save(self, path: Path | None = None) -> None:
        target = path or self._path
        if target is None:
            raise ValueError("no file name: use save(path)")
        api.save(self._project, target)
        self._path = target
        self._mark_saved()
        self.changed.emit()

    # ----------------------------------------------------------- helpers

    @staticmethod
    def _untitled() -> api.Project:
        project = api.new_project("Untitled")
        api.add_level(project, "Ground floor", 0.0)
        api.clear_history(project)
        return project

    def _replace(self, project: api.Project, path: Path | None) -> None:
        self._project = project
        self._path = path
        self._selected = None
        self._mark_saved()
        self.selection_changed.emit()
        self.changed.emit()

    def _top_step(self) -> object | None:
        return api.current_step(self._project)

    def _mark_saved(self) -> None:
        self._saved_step = self._top_step()

    def _drop_missing_selection(self) -> None:
        if self._selected is not None and self.kind_of(self._selected) is None:
            self.select(None)

    def kind_of(self, element_id: UUID) -> str | None:
        """'level', 'wall', 'door', 'window', or None if no such element exists."""
        p = self._project
        if any(lv.id == element_id for lv in p.levels):
            return "level"
        if any(w.id == element_id for w in p.walls):
            return "wall"
        for e in p.hosted:
            if e.id == element_id:
                return e.kind
        if any(r.id == element_id for r in p.references):
            return "reference"
        return None
