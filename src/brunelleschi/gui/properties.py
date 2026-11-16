"""The properties panel: the parameters of the selected element, editable.

Every edit is a command (through ``Document.edit``), so it is checked, undoable, and a
refused value is replaced by the model's value with the reason shown under the fields.
Numbers accept a decimal comma.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from brunelleschi import api
from brunelleschi.gui.document import Document


def parse_metres(text: str) -> float:
    """A number of metres; a decimal comma is accepted. Raises ValueError."""
    return float(text.strip().replace(",", "."))


def fmt(value: float) -> str:
    return f"{value:.3f}"


class PropertiesPanel(QWidget):
    def __init__(self, document: Document) -> None:
        super().__init__()
        self.document = document
        self._layout = QVBoxLayout(self)
        self.heading = QLabel()
        self.heading.setStyleSheet("font-weight: bold")
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #b00020")
        self._layout.addWidget(self.heading)
        self._layout.addWidget(self.form_host)
        self._layout.addWidget(self.message)
        self._layout.addStretch(1)
        self.fields: dict[str, QLineEdit | QComboBox] = {}
        self._refreshers: list[Callable[[], None]] = []
        self._shown: UUID | None = None
        document.selection_changed.connect(self.rebuild)
        document.changed.connect(self.refresh)
        document.error.connect(self.message.setText)
        self.rebuild()

    # ------------------------------------------------------------ build

    def rebuild(self) -> None:
        # Replace the whole form: its fields may be in the middle of one of their own
        # signals, so the old ones are deleted later by Qt, never right here.
        old = self.form_host
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self._layout.replaceWidget(old, self.form_host)
        old.hide()
        old.deleteLater()
        self.fields.clear()
        self._refreshers.clear()
        self.message.clear()
        selected = self.document.selected
        self._shown = selected
        kind = self.document.kind_of(selected) if selected else None
        if kind is None:
            self.heading.setText("No selection")
            return
        assert selected is not None
        builder = {
            "level": self._build_level,
            "wall": self._build_wall,
            "door": self._build_hosted,
            "window": self._build_hosted,
        }[kind]
        builder(selected)
        self.refresh()

    def refresh(self) -> None:
        """Show the model's current values (after an edit, an undo or a refusal)."""
        if self._shown is not None and self.document.kind_of(self._shown) is None:
            self.rebuild()
            return
        for refresher in self._refreshers:
            refresher()

    # --------------------------------------------------------- helpers

    def _number(
        self,
        name: str,
        label: str,
        read: Callable[[], float | None],
        write: Callable[[float], object],
    ) -> QLineEdit:
        edit = QLineEdit()
        edit.setObjectName(name)

        def show() -> None:
            value = read()
            edit.blockSignals(True)
            edit.setEnabled(value is not None)
            edit.setText("" if value is None else fmt(value))
            edit.blockSignals(False)

        def commit() -> None:
            value = read()
            try:
                number = parse_metres(edit.text())
            except ValueError:
                self.message.setText(f"{label}: not a number of metres: {edit.text()!r}")
                show()
                return
            if value is not None and abs(number - value) < 1e-9:
                return
            self.message.clear()
            self.document.edit(lambda: write(number))

        edit.editingFinished.connect(commit)
        self._refreshers.append(show)
        self.form.addRow(label, edit)
        self.fields[name] = edit
        return edit

    def _text(
        self, name: str, label: str, read: Callable[[], str], write: Callable[[str], object]
    ) -> QLineEdit:
        edit = QLineEdit()
        edit.setObjectName(name)

        def show() -> None:
            edit.blockSignals(True)
            edit.setText(read())
            edit.blockSignals(False)

        def commit() -> None:
            if edit.text() != read():
                self.message.clear()
                self.document.edit(lambda: write(edit.text()))

        edit.editingFinished.connect(commit)
        self._refreshers.append(show)
        self.form.addRow(label, edit)
        self.fields[name] = edit
        return edit

    def _choice(
        self,
        name: str,
        label: str,
        options: Callable[[], list[tuple[str, str]]],
        read: Callable[[], str],
        write: Callable[[str], object],
    ) -> QComboBox:
        """A combo box of (value, text) options."""
        combo = QComboBox()
        combo.setObjectName(name)

        def show() -> None:
            combo.blockSignals(True)
            combo.clear()
            for value, text in options():
                combo.addItem(text, value)
            current = read()
            combo.setEnabled(current != "")  # "" means: does not apply to this element
            combo.setCurrentIndex(max(combo.findData(current), 0) if current else -1)
            combo.blockSignals(False)

        def commit() -> None:
            value = combo.currentData()
            if value is not None and value != read():
                self.message.clear()
                self.document.edit(lambda: write(value))

        combo.currentIndexChanged.connect(commit)
        self._refreshers.append(show)
        self.form.addRow(label, combo)
        self.fields[name] = combo
        return combo

    def _info(self, label: str, read: Callable[[], str]) -> None:
        value = QLabel()

        def show() -> None:
            value.setText(read())

        self._refreshers.append(show)
        self.form.addRow(label, value)

    def _levels(self) -> list[tuple[str, str]]:
        p = self.document.project
        return [(str(lv.id), lv.name) for lv in reversed(p.levels_by_elevation())]

    # ---------------------------------------------------------- kinds

    def _build_level(self, level_id: UUID) -> None:
        p = self.document.project
        self.heading.setText("Level")
        self._text(
            "name",
            "Name",
            lambda: p.level(level_id).name,
            lambda text: api.rename_level(p, level_id, text),
        )
        self._number(
            "elevation",
            "Elevation (m)",
            lambda: p.level(level_id).elevation,
            lambda v: api.set_level_elevation(p, level_id, v),
        )
        self._info("Walls bound", lambda: str(len(p.walls_on_level(level_id))))

    def _build_wall(self, wall_id: UUID) -> None:
        p = self.document.project
        self.heading.setText(f"Wall {api.short_id(wall_id)}")

        def wall() -> api.Wall:
            return p.wall(wall_id)

        def top_level() -> float | None:
            top = wall().top
            return top.offset if isinstance(top, api.TopAtLevel) else None

        def unconnected() -> float | None:
            top = wall().top
            return top.height if isinstance(top, api.UnconnectedHeight) else None

        def top_level_id() -> str:
            top = wall().top
            return str(top.level_id) if isinstance(top, api.TopAtLevel) else ""

        def top_mode() -> str:
            return "level" if isinstance(wall().top, api.TopAtLevel) else "height"

        def set_top_mode(mode: str) -> object:
            if mode == "level":
                above = [
                    lv for lv in p.levels_by_elevation() if lv.elevation > p.wall_z_range(wall())[0]
                ]
                if not above:
                    raise api.ModelError("no level above the wall base to bind the top to")
                return api.modify_wall(p, wall_id, top_level=above[0].id)
            base, top = p.wall_z_range(wall())
            return api.modify_wall(p, wall_id, height=top - base)

        self._number(
            "start_x",
            "Start X (m)",
            lambda: wall().start.x,
            lambda v: api.modify_wall(p, wall_id, start=(v, wall().start.y)),
        )
        self._number(
            "start_y",
            "Start Y (m)",
            lambda: wall().start.y,
            lambda v: api.modify_wall(p, wall_id, start=(wall().start.x, v)),
        )
        self._number(
            "end_x",
            "End X (m)",
            lambda: wall().end.x,
            lambda v: api.modify_wall(p, wall_id, end=(v, wall().end.y)),
        )
        self._number(
            "end_y",
            "End Y (m)",
            lambda: wall().end.y,
            lambda v: api.modify_wall(p, wall_id, end=(wall().end.x, v)),
        )
        self._number(
            "thickness",
            "Thickness (m)",
            lambda: wall().thickness,
            lambda v: api.modify_wall(p, wall_id, thickness=v),
        )
        self._choice(
            "base_level",
            "Base level",
            self._levels,
            lambda: str(wall().base_level_id),
            lambda v: api.modify_wall(p, wall_id, base_level=UUID(v)),
        )
        self._number(
            "base_offset",
            "Base offset (m)",
            lambda: wall().base_offset,
            lambda v: api.modify_wall(p, wall_id, base_offset=v),
        )
        self._choice(
            "top_mode",
            "Top",
            lambda: [("level", "bound to a level"), ("height", "unconnected height")],
            top_mode,
            set_top_mode,
        )
        self._choice(
            "top_level",
            "Top level",
            self._levels,
            top_level_id,
            lambda v: api.modify_wall(p, wall_id, top_level=UUID(v)),
        )
        self._number(
            "top_offset",
            "Top offset (m)",
            top_level,
            lambda v: api.modify_wall(p, wall_id, top_offset=v),
        )
        self._number(
            "height", "Height (m)", unconnected, lambda v: api.modify_wall(p, wall_id, height=v)
        )
        self._info("Length", lambda: f"{wall().length:.3f} m")
        self._info("Elevations", lambda: "{:+.3f} .. {:+.3f} m".format(*p.wall_z_range(wall())))

    def _build_hosted(self, element_id: UUID) -> None:
        p = self.document.project

        def element() -> api.HostedElement:
            return p.hosted_element(element_id)

        self.heading.setText(f"{element().kind.capitalize()} {api.short_id(element_id)}")
        self._info("Wall", lambda: api.short_id(element().host_id))
        self._number(
            "position",
            "Position (m)",
            lambda: element().position,
            lambda v: api.modify_hosted(p, element_id, position=v),
        )
        self._number(
            "width",
            "Width (m)",
            lambda: element().width,
            lambda v: api.modify_hosted(p, element_id, width=v),
        )
        self._number(
            "height",
            "Height (m)",
            lambda: element().height,
            lambda v: api.modify_hosted(p, element_id, height=v),
        )
        self._number(
            "sill_height",
            "Sill height (m)",
            lambda: element().sill_height,
            lambda v: api.modify_hosted(p, element_id, sill_height=v),
        )
        if isinstance(element(), api.Door):

            def door() -> api.Door:
                e = element()
                assert isinstance(e, api.Door)
                return e

            self._choice(
                "swing_side",
                "Opens to",
                lambda: [("left", "left side"), ("right", "right side")],
                lambda: str(door().swing_side),
                lambda v: api.modify_hosted(p, element_id, swing_side=v),
            )
            self._choice(
                "hinge",
                "Hinges at",
                lambda: [("start", "start jamb"), ("end", "end jamb")],
                lambda: str(door().hinge),
                lambda v: api.modify_hosted(p, element_id, hinge=v),
            )
