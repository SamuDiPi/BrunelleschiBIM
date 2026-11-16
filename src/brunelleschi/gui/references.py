"""Loading the IFC files a project links to, without blocking the window.

The project stores links (``api.IfcReference``); this keeps the loaded content. Paths are
resolved against the project file's folder. Files load in a worker thread; when one is
ready, ``loaded`` is emitted and the plan and the 3D view redraw.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QObject, QThread, Signal

from brunelleschi.gui.document import Document

LOADING = "loading"


def resolve(document: Document, stored: str) -> Path:
    """The file a stored link points to."""
    path = Path(stored)
    if path.is_absolute() or document.path is None:
        return path
    return (document.path.parent / path).resolve()


def path_to_store(document: Document, chosen: Path) -> str:
    """Relative to the project file's folder when possible (the project stays movable),
    absolute otherwise (project not saved yet, or another drive)."""
    if document.path is not None:
        try:
            return Path(
                os.path.relpath(chosen.resolve(), document.path.parent.resolve())
            ).as_posix()
        except ValueError:  # different drives on Windows
            pass
    return chosen.resolve().as_posix()


class _Worker(QThread):
    done = Signal(object, object)  # reference id, ReferenceModel or error message

    def __init__(self, reference_id: UUID, path: Path) -> None:
        super().__init__()
        self.reference_id = reference_id
        self.path = path

    def run(self) -> None:
        from brunelleschi.ifc.reference import ReferenceError, load_reference

        try:
            result: object = load_reference(self.path)
        except ReferenceError as exc:
            result = str(exc)
        except Exception as exc:  # a broken file must not take the window down
            result = f"cannot read {self.path.name}: {exc}"
        self.done.emit(self.reference_id, result)


class References(QObject):
    """Loaded content of the project's IFC links, kept in step with the project."""

    loaded = Signal(object)  # reference id

    def __init__(self, document: Document, synchronous: bool = False) -> None:
        super().__init__()
        self.document = document
        self.synchronous = synchronous
        # reference id -> (resolved path, ReferenceModel | error message | LOADING)
        self.state: dict[UUID, tuple[Path, object]] = {}
        self._workers: dict[UUID, _Worker] = {}
        self._sections: dict[tuple[UUID, UUID, float], list[NDArray[np.float64]]] = {}
        document.changed.connect(self.sync)
        self.sync()

    # ----------------------------------------------------------- loading

    def sync(self) -> None:
        wanted = {r.id: resolve(self.document, r.path) for r in self.document.project.references}
        for ref_id in list(self.state):
            if ref_id not in wanted or self.state[ref_id][0] != wanted[ref_id]:
                del self.state[ref_id]
                self._sections = {k: v for k, v in self._sections.items() if k[0] != ref_id}
        for ref_id, path in wanted.items():
            if ref_id not in self.state:
                self._load(ref_id, path)

    def _load(self, ref_id: UUID, path: Path) -> None:
        self.state[ref_id] = (path, LOADING)
        worker = _Worker(ref_id, path)
        worker.done.connect(self._finished)
        if self.synchronous:
            worker.run()
            return
        self._workers[ref_id] = worker
        worker.start()

    def _finished(self, ref_id: UUID, result: object) -> None:
        self._workers.pop(ref_id, None)
        if ref_id in self.state:
            self.state[ref_id] = (self.state[ref_id][0], result)
            self.loaded.emit(ref_id)

    def wait(self) -> None:
        """Block until every load has finished (for tests and shutdown)."""
        for worker in list(self._workers.values()):
            worker.wait()

    # ----------------------------------------------------------- queries

    def model(self, ref_id: UUID) -> object:
        """The ReferenceModel, an error message, LOADING, or None."""
        entry = self.state.get(ref_id)
        return entry[1] if entry else None

    def status(self, ref_id: UUID) -> str:
        from brunelleschi.ifc.reference import ReferenceModel

        value = self.model(ref_id)
        if isinstance(value, ReferenceModel):
            return value.summary()
        if value == LOADING:
            return "loading..."
        return str(value) if value is not None else "not loaded"

    def models(self) -> list[tuple[UUID, object]]:
        from brunelleschi.ifc.reference import ReferenceModel

        return [(k, v[1]) for k, v in self.state.items() if isinstance(v[1], ReferenceModel)]

    def plan_lines(self, level_id: UUID, z: float) -> list[NDArray[np.float64]]:
        """Section segments at elevation ``z`` of the reference elements whose storey
        matches ``level_id``, one (k, 2, 2) array per element."""
        from brunelleschi.ifc.reference import ReferenceModel, match_storeys, section

        project = self.document.project
        levels = [(lv.id, lv.name, lv.elevation) for lv in project.levels]
        result: list[NDArray[np.float64]] = []
        for ref_id, model in self.models():
            assert isinstance(model, ReferenceModel)
            key = (ref_id, level_id, round(z, 6))
            if key not in self._sections:
                matches = match_storeys(model.storeys, levels)
                on_level = {gid for gid, lv in matches.items() if lv == level_id}
                self._sections[key] = [
                    seg
                    for e in model.elements
                    if e.storey in on_level and len(seg := section(e.vertices, e.triangles, z))
                ]
            result.extend(self._sections[key])
        return result

    def storey_matches(self, ref_id: UUID) -> list[tuple[str, float, str | None]]:
        """(storey name, elevation, matched level name or None) for the properties panel."""
        from brunelleschi.ifc.reference import ReferenceModel, match_storeys

        model = self.model(ref_id)
        if not isinstance(model, ReferenceModel):
            return []
        project = self.document.project
        levels = [(lv.id, lv.name, lv.elevation) for lv in project.levels]
        matches = match_storeys(model.storeys, levels)
        names = {lv.id: lv.name for lv in project.levels}
        return [
            (s.name, s.elevation, names.get(matches.get(s.global_id)))  # type: ignore[arg-type]
            for s in model.storeys
        ]
