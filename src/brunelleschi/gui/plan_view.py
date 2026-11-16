"""The 2D plan of the current level, drawn with QPainter, with editing tools.

It draws the same primitives as the SVG plan (``brunelleschi.drawings``), so what is on
screen is what gets printed. Pens are cosmetic: line widths are in screen pixels and do
not change with zoom.

Mouse: the left button belongs to the current tool; the wheel zooms at the cursor; the
middle button, or the right button dragged, pans; a right click (without dragging)
ends what the tool is doing, like Esc.
"""

from __future__ import annotations

import math
from uuid import UUID

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPolygonF,
    QResizeEvent,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from brunelleschi import api
from brunelleschi.drawings.primitives import Arc, Area, Drawing, Line
from brunelleschi.gui.document import Document
from brunelleschi.gui.snap import Vec
from brunelleschi.gui.tools import OpeningTool, SelectTool, Tool, WallTool

POCHE = QColor("#a6a6a6")
HIGHLIGHT = QColor("#1f6fd1")
SNAP_MARK = QColor("#d1491f")
# Layer -> (pen width in pixels, dashed)
PENS: dict[str, tuple[float, bool]] = {
    "wall-projection": (1.0, False),
    "wall-cut-outline": (2.0, False),
    "opening-above": (1.0, True),
    "window": (1.2, False),
    "door": (1.6, False),
    "door-swing": (1.0, False),
}
MARGIN_PX = 40
CLICK_PX = 4  # a press and release closer than this is a click, not a drag


def _arc_points(arc: Arc, segments: int = 24) -> list[QPointF]:
    cx, cy = arc.centre
    a0 = math.atan2(arc.start[1] - cy, arc.start[0] - cx)
    a1 = math.atan2(arc.end[1] - cy, arc.end[0] - cx)
    sweep = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    r = math.hypot(arc.start[0] - cx, arc.start[1] - cy)
    return [
        QPointF(
            cx + r * math.cos(a0 + sweep * i / segments),
            cy + r * math.sin(a0 + sweep * i / segments),
        )
        for i in range(segments + 1)
    ]


def _pen(colour: QColor, width: float, dashed: bool = False) -> QPen:
    pen = QPen(colour, width)
    pen.setCosmetic(True)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    if dashed:
        pen.setStyle(Qt.PenStyle.DashLine)
    return pen


class PlanView(QWidget):
    """Plan of one level, with the current tool."""

    status_changed = Signal(str)  # cursor position, snap and tool hint
    tool_changed = Signal(str)

    def __init__(self, document: Document) -> None:
        super().__init__()
        self.document = document
        self.level_id: UUID | None = None
        self.drawing = Drawing(())
        self.revision = 0  # increases every time the drawing is rebuilt (for tests)
        self.scale = 50.0  # pixels per metre
        self._centre = (0.0, 0.0)  # model point at the widget centre
        self._pan: QPointF | None = None
        self._right_press: QPointF | None = None
        self._fitted = False
        # Settings the tools read.
        self.grid: float | None = 0.10
        self.ortho = False
        self.wall_thickness = 0.30
        self.wall_height = 3.00
        self.tool: Tool = SelectTool(self)
        self.setMinimumSize(320, 240)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        document.changed.connect(self.rebuild)
        document.selection_changed.connect(self.update)

    # ------------------------------------------------------------ tools

    def set_tool(self, name: str) -> None:
        self.tool.cancel()
        tools: dict[str, Tool] = {
            "select": SelectTool(self),
            "wall": WallTool(self),
            "door": OpeningTool(self, "door"),
            "window": OpeningTool(self, "window"),
        }
        self.tool = tools[name]
        self.setCursor(self.tool.cursor)
        self.tool_changed.emit(name)
        self.status_changed.emit(self.tool.status())
        self.update()

    def ortho_active(self, modifiers: Qt.KeyboardModifier) -> bool:
        return self.ortho != bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

    def cancel(self) -> None:
        """Esc: stop the tool's action; if there is none, go back to selecting."""
        if not self.tool.cancel() and self.tool.name != "select":
            self.set_tool("select")
        self.update()

    # ---------------------------------------------------------- content

    def set_level(self, level_id: UUID | None) -> None:
        self.level_id = level_id
        self._fitted = False
        self.rebuild()

    def rebuild(self) -> None:
        project = self.document.project
        ids = {lv.id for lv in project.levels}
        if self.level_id not in ids:
            levels = project.levels_by_elevation()
            self.level_id = levels[0].id if levels else None
            self._fitted = False
        if self.level_id is None:
            self.drawing = Drawing(())
        else:
            self.drawing = api.plan_view(project, self.level_id)
        self.revision += 1
        if not self._fitted:
            self.fit()
        self.update()

    # ------------------------------------------------------------- view

    def fit(self) -> None:
        extent = self.drawing.extent()
        if extent is None:
            self._centre, self.scale = (0.0, 0.0), 50.0
        else:
            x0, y0, x1, y1 = extent
            w = max(x1 - x0, 1.0)
            h = max(y1 - y0, 1.0)
            avail_w = max(self.width() - 2 * MARGIN_PX, 50)
            avail_h = max(self.height() - 2 * MARGIN_PX, 50)
            self.scale = min(avail_w / w, avail_h / h)
            self._centre = ((x0 + x1) / 2, (y0 + y1) / 2)
        self._fitted = True
        self.update()

    def set_view(self, centre: Vec, scale: float) -> None:
        """Show ``centre`` in the middle at ``scale`` pixels per metre."""
        self._centre, self.scale, self._fitted = centre, scale, True
        self.update()

    def transform(self) -> QTransform:
        """Model metres (y up) to widget pixels (y down)."""
        t = QTransform()
        t.translate(self.width() / 2, self.height() / 2)
        t.scale(self.scale, -self.scale)
        t.translate(-self._centre[0], -self._centre[1])
        return t

    def to_model(self, point: QPointF) -> Vec:
        inverted, _ = self.transform().inverted()
        p = inverted.map(point)
        return (p.x(), p.y())

    def to_screen(self, point: Vec) -> QPointF:
        return self.transform().map(QPointF(point[0], point[1]))

    def visible_rect(self) -> QRectF:
        inverted, _ = self.transform().inverted()
        return inverted.mapRect(QRectF(self.rect()))

    # ----------------------------------------------------------- events

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.2 ** (event.angleDelta().y() / 120)
        before = self.to_model(event.position())
        self.scale = min(max(self.scale * factor, 0.5), 5000.0)
        after = self.to_model(event.position())
        self._centre = (
            self._centre[0] + before[0] - after[0],
            self._centre[1] + before[1] - after[1],
        )
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        button = event.button()
        if button == Qt.MouseButton.LeftButton:
            self.tool.press(self.to_model(event.position()), event.modifiers())
        elif button in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._pan = event.position()
            if button == Qt.MouseButton.RightButton:
                self._right_press = event.position()
        self._report(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan is not None:
            delta = event.position() - self._pan
            self._pan = event.position()
            self._centre = (
                self._centre[0] - delta.x() / self.scale,
                self._centre[1] + delta.y() / self.scale,
            )
            self.update()
            return
        self.tool.move(self.to_model(event.position()), event.modifiers())
        self._report(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        button = event.button()
        if button == Qt.MouseButton.LeftButton:
            self.tool.release(self.to_model(event.position()), event.modifiers())
        elif button == Qt.MouseButton.RightButton and self._right_press is not None:
            moved = event.position() - self._right_press
            if math.hypot(moved.x(), moved.y()) < CLICK_PX:
                self.cancel()
            self._right_press = None
        self._pan = None
        self._report(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        if not self._fitted:
            self.fit()

    def _report(self, event: QMouseEvent) -> None:
        x, y = self.to_model(event.position())
        snapped = self.tool.snapped
        where = f"x {x:.2f}  y {y:.2f}"
        if snapped is not None:
            where = f"x {snapped.point[0]:.2f}  y {snapped.point[1]:.2f}  [{snapped.kind}]"
        hint = self.tool.status()
        self.status_changed.emit(f"{where}    {hint}" if hint else where)

    # ----------------------------------------------------------- paint

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("white"))
        painter.setTransform(self.transform())
        for primitive in self.drawing.primitives:
            if isinstance(primitive, Area):
                path = QPainterPath()
                path.setFillRule(Qt.FillRule.OddEvenFill)
                for ring in primitive.rings:
                    path.addPolygon(QPolygonF([QPointF(x, y) for x, y in ring]))
                    path.closeSubpath()
                painter.fillPath(path, QBrush(POCHE))
                continue
            width, dashed = PENS.get(primitive.layer, (1.0, False))
            painter.setPen(_pen(QColor("black"), width, dashed))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if isinstance(primitive, Line):
                points = [QPointF(x, y) for x, y in primitive.points]
                if primitive.closed:
                    painter.drawPolygon(QPolygonF(points))
                else:
                    painter.drawPolyline(QPolygonF(points))
            else:
                painter.drawPolyline(QPolygonF(_arc_points(primitive)))
        self._paint_selection(painter)
        self.tool.paint(painter)
        self._paint_snap(painter)
        painter.end()

    def _paint_selection(self, painter: QPainter) -> None:
        selected = self.document.selected
        if selected is None:
            return
        geometry = api.wall_geometry(self.document.project)
        outline: tuple[tuple[float, float], ...] | None = None
        if selected in geometry.footprints:
            outline = geometry.footprints[selected].corners
        elif selected in geometry.openings:
            outline = geometry.openings[selected].corners
        if outline is None:
            return
        painter.setPen(_pen(HIGHLIGHT, 3.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in outline]))

    def paint_grips(self, painter: QPainter, points: list[Vec]) -> None:
        """Small filled squares at wall ends, sized in pixels."""
        painter.save()
        painter.resetTransform()
        painter.setPen(_pen(HIGHLIGHT, 1.0))
        painter.setBrush(QBrush(QColor("white")))
        for p in points:
            s = self.to_screen(p)
            painter.drawRect(QRectF(s.x() - 4, s.y() - 4, 8, 8))
        painter.restore()

    def _paint_snap(self, painter: QPainter) -> None:
        snapped = self.tool.snapped
        if snapped is None:
            return
        painter.save()
        painter.resetTransform()
        painter.setPen(_pen(SNAP_MARK, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        s = self.to_screen(snapped.point)
        x, y = s.x(), s.y()
        if snapped.kind == "endpoint":
            painter.drawRect(QRectF(x - 5, y - 5, 10, 10))
        elif snapped.kind == "on wall":
            painter.drawLine(QPointF(x - 5, y - 5), QPointF(x + 5, y + 5))
            painter.drawLine(QPointF(x - 5, y + 5), QPointF(x + 5, y - 5))
        else:
            painter.drawLine(QPointF(x - 5, y), QPointF(x + 5, y))
            painter.drawLine(QPointF(x, y - 5), QPointF(x, y + 5))
        painter.restore()
