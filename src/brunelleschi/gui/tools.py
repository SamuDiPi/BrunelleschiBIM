"""Plan tools: select and move, draw walls, place doors and windows.

A tool receives clicks and moves already converted to model metres, decides what the
click means (with ``snap``), previews it, and turns it into API commands through
``Document.edit``, so each completed action is one undo step.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING
from uuid import UUID

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from brunelleschi import api
from brunelleschi.gui.snap import Snap, Vec, along_wall, grip_at, pick, snap

if TYPE_CHECKING:
    from brunelleschi.gui.document import Document
    from brunelleschi.gui.plan_view import PlanView

PREVIEW = QColor("#1f6fd1")
SNAP_PX = 10  # snap and pick tolerance, in screen pixels

DOOR_SIZE = (0.90, 2.10, 0.0)  # width, height, sill
WINDOW_SIZE = (1.20, 1.40, 0.90)


def _pen(width: float = 1.5, dashed: bool = False) -> QPen:
    pen = QPen(PREVIEW, width)
    pen.setCosmetic(True)
    if dashed:
        pen.setStyle(Qt.PenStyle.DashLine)
    return pen


class Tool:
    """Base class: a tool does nothing until it overrides a method."""

    name = "tool"
    cursor = Qt.CursorShape.ArrowCursor

    def __init__(self, view: PlanView) -> None:
        self.view = view
        self.snapped: Snap | None = None

    @property
    def document(self) -> Document:
        return self.view.document

    @property
    def project(self) -> api.Project:
        return self.view.document.project

    def tolerance(self) -> float:
        return SNAP_PX / self.view.scale

    def press(self, point: Vec, modifiers: Qt.KeyboardModifier) -> None: ...

    def move(self, point: Vec, modifiers: Qt.KeyboardModifier) -> None: ...

    def release(self, point: Vec, modifiers: Qt.KeyboardModifier) -> None: ...

    def cancel(self) -> bool:
        """Esc or right click: stop what is in progress. False if there was nothing."""
        return False

    def paint(self, painter: QPainter) -> None: ...

    def status(self) -> str:
        return ""


# ------------------------------------------------------------------ select


class SelectTool(Tool):
    """Click to select; drag a wall, one of its end grips, or a door or window to move it."""

    name = "select"

    def __init__(self, view: PlanView) -> None:
        super().__init__(view)
        self._drag: tuple[str, UUID, str | None, Vec] | None = None  # kind, id, end, start
        self._target: Vec | None = None

    def press(self, point: Vec, modifiers: Qt.KeyboardModifier) -> None:
        tol = self.tolerance()
        selected = self.document.selected
        if selected is not None and self.document.kind_of(selected) == "wall":
            end = grip_at(self.project.wall(selected), point, tol)
            if end is not None:
                self._drag = ("end", selected, end, point)
                return
        picked = pick(self.project, point, tolerance=tol, level=self.view.level_id)
        self.document.select(picked)
        if picked is not None:
            kind = self.document.kind_of(picked)
            grab = point
            if kind == "wall":
                # Grab on the grid, so that the move is a whole number of grid steps.
                grab = snap(self.project, point, tolerance=0.0, grid=self.view.grid).point
            self._drag = (kind or "", picked, None, grab)
        self._target = None

    def move(self, point: Vec, modifiers: Qt.KeyboardModifier) -> None:
        if self._drag is None:
            return
        kind, element_id, end, start = self._drag
        tol = self.tolerance()
        ortho = self.view.ortho_active(modifiers)
        if kind == "end":
            wall = self.project.wall(element_id)
            fixed = wall.end if end == "start" else wall.start
            self.snapped = snap(
                self.project,
                point,
                tolerance=tol,
                grid=self.view.grid,
                anchor=(fixed.x, fixed.y),
                ortho=ortho,
                exclude=frozenset({element_id}),
            )
            self._target = self.snapped.point
        elif kind == "wall":
            self.snapped = snap(
                self.project,
                point,
                tolerance=tol,
                grid=self.view.grid,
                anchor=start,
                ortho=ortho,
                exclude=frozenset({element_id}),
            )
            self._target = self.snapped.point
        else:  # a door or window slides along its wall
            self._target = point
        self.view.update()

    def release(self, point: Vec, modifiers: Qt.KeyboardModifier) -> None:
        drag, target = self._drag, self._target
        self._drag, self._target, self.snapped = None, None, None
        if drag is None or target is None:
            self.view.update()
            return
        kind, element_id, end, start = drag
        p = self.project
        if math.hypot(target[0] - start[0], target[1] - start[1]) < 1e-6:
            self.view.update()
            return
        if kind == "end" and end is not None:
            self.document.edit(lambda: api.move_wall_end(p, element_id, end, target))
        elif kind == "wall":
            dx, dy = round(target[0] - start[0], 6), round(target[1] - start[1], 6)
            self.document.edit(lambda: api.move_wall(p, element_id, dx, dy))
        elif kind in ("door", "window"):
            element = p.hosted_element(element_id)
            distance, _ = along_wall(p.wall(element.host_id), target)
            step = self.view.grid or 0.01
            position = round(round(distance / step) * step, 6)
            self.document.edit(lambda: api.modify_hosted(p, element_id, position=position))
        self.view.update()

    def cancel(self) -> bool:
        if self._drag is not None:
            self._drag, self._target, self.snapped = None, None, None
            self.view.update()
            return True
        if self.document.selected is not None:
            self.document.select(None)
            return True
        return False

    def paint(self, painter: QPainter) -> None:
        selected = self.document.selected
        if selected is not None and self.document.kind_of(selected) == "wall":
            wall = self.project.wall(selected)
            self.view.paint_grips(painter, [(wall.start.x, wall.start.y), (wall.end.x, wall.end.y)])
        if self._drag is None or self._target is None:
            return
        kind, element_id, end, start = self._drag
        painter.setPen(_pen(1.5, dashed=True))
        if kind == "end":
            wall = self.project.wall(element_id)
            fixed = wall.end if end == "start" else wall.start
            painter.drawLine(QPointF(fixed.x, fixed.y), QPointF(*self._target))
        elif kind == "wall":
            wall = self.project.wall(element_id)
            dx, dy = self._target[0] - start[0], self._target[1] - start[1]
            painter.drawLine(
                QPointF(wall.start.x + dx, wall.start.y + dy),
                QPointF(wall.end.x + dx, wall.end.y + dy),
            )


# -------------------------------------------------------------------- wall


class WallTool(Tool):
    """Click the start, then each next point: walls are drawn in a chain, each one an undo
    step. Esc or a right click ends the chain."""

    name = "wall"
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, view: PlanView) -> None:
        super().__init__(view)
        self.anchor: Vec | None = None

    def _snap(self, point: Vec, modifiers: Qt.KeyboardModifier) -> Snap:
        return snap(
            self.project,
            point,
            tolerance=self.tolerance(),
            grid=self.view.grid,
            anchor=self.anchor,
            ortho=self.view.ortho_active(modifiers),
        )

    def move(self, point: Vec, modifiers: Qt.KeyboardModifier) -> None:
        self.snapped = self._snap(point, modifiers)
        self.view.update()

    def press(self, point: Vec, modifiers: Qt.KeyboardModifier) -> None:
        target = self._snap(point, modifiers).point
        if self.anchor is None:
            self.anchor = target
            return
        if math.hypot(target[0] - self.anchor[0], target[1] - self.anchor[1]) < 1e-6:
            return
        start, p = self.anchor, self.project
        level_id = self.view.level_id
        if level_id is None:
            self.document.error.emit("add a level first")
            return
        base = p.level(level_id)
        above = [lv for lv in p.levels_by_elevation() if lv.elevation > base.elevation]
        thickness = self.view.wall_thickness

        def add() -> object:
            if above:
                return api.add_wall(p, start, target, thickness, base.id, top_level=above[0].id)
            return api.add_wall(p, start, target, thickness, base.id, height=self.view.wall_height)

        if self.document.edit(add):
            self.anchor = target  # continue the chain from here

    def cancel(self) -> bool:
        if self.anchor is None:
            return False
        self.anchor = None
        self.view.update()
        return True

    def paint(self, painter: QPainter) -> None:
        if self.anchor is None or self.snapped is None:
            return
        a, b = self.anchor, self.snapped.point
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        painter.setPen(_pen(1.0, dashed=True))
        painter.drawLine(QPointF(*a), QPointF(*b))
        if length > 1e-6:
            half = self.view.wall_thickness / 2
            nx, ny = -(b[1] - a[1]) / length * half, (b[0] - a[0]) / length * half
            painter.setPen(_pen(1.5))
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(a[0] + nx, a[1] + ny),
                        QPointF(b[0] + nx, b[1] + ny),
                        QPointF(b[0] - nx, b[1] - ny),
                        QPointF(a[0] - nx, a[1] - ny),
                    ]
                )
            )

    def status(self) -> str:
        if self.anchor is None or self.snapped is None:
            return "Wall: click the start point"
        a, b = self.anchor, self.snapped.point
        return (
            f"Wall: length {math.hypot(b[0] - a[0], b[1] - a[1]):.2f} m (right click or Esc ends)"
        )


# --------------------------------------------------------- door and window


class OpeningTool(Tool):
    """Click on a wall to place a door or window there. A door opens towards the side of
    the wall that was clicked."""

    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, view: PlanView, kind: str) -> None:
        super().__init__(view)
        self.kind = kind
        self.name = kind
        self._preview: tuple[UUID, float, str] | None = None

    def _size(self) -> tuple[float, float, float]:
        return DOOR_SIZE if self.kind == "door" else WINDOW_SIZE

    def _place(self, point: Vec) -> tuple[UUID, float, str] | None:
        picked = pick(self.project, point, tolerance=self.tolerance(), level=self.view.level_id)
        if picked is None:
            return None
        if self.document.kind_of(picked) != "wall":
            picked = self.project.hosted_element(picked).host_id
        wall = self.project.wall(picked)
        distance, side = along_wall(wall, point)
        width = self._size()[0]
        if wall.length < width:
            return (wall.id, wall.length / 2, side)
        step = self.view.grid or 0.01
        position = min(
            max(round(round(distance / step) * step, 6), width / 2), wall.length - width / 2
        )
        return (wall.id, position, side)

    def move(self, point: Vec, modifiers: Qt.KeyboardModifier) -> None:
        self._preview = self._place(point)
        self.view.update()

    def press(self, point: Vec, modifiers: Qt.KeyboardModifier) -> None:
        placed = self._place(point)
        if placed is None:
            self.document.error.emit(f"click on a wall to place a {self.kind}")
            return
        wall_id, position, side = placed
        width, height, sill = self._size()
        p = self.project
        if self.kind == "door":
            self.document.edit(
                lambda: api.add_door(
                    p, wall_id, position, width, height, sill_height=sill, swing_side=side
                )
            )
        else:
            self.document.edit(lambda: api.add_window(p, wall_id, position, width, height, sill))

    def paint(self, painter: QPainter) -> None:
        if self._preview is None:
            return
        wall_id, position, _ = self._preview
        wall = self.project.wall(wall_id)
        width = self._size()[0]
        dx, dy = (
            (wall.end.x - wall.start.x) / wall.length,
            (wall.end.y - wall.start.y) / wall.length,
        )
        half = wall.thickness / 2
        a, b = position - width / 2, position + width / 2
        corners = [
            (wall.start.x + dx * s - dy * h, wall.start.y + dy * s + dx * h)
            for s, h in ((a, -half), (b, -half), (b, half), (a, half))
        ]
        painter.setPen(_pen(2.0))
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in corners]))

    def status(self) -> str:
        return f"{self.kind.capitalize()}: click on a wall"
