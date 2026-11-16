"""The 2D plan of the current level, drawn with QPainter (read-only in M10).

It draws the same primitives as the SVG plan (``brunelleschi.drawings``), so what is on
screen is what gets printed. Pens are cosmetic: line widths are in screen pixels and do
not change with zoom.
"""

from __future__ import annotations

import math
from uuid import UUID

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPolygonF,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from brunelleschi import api
from brunelleschi.drawings.primitives import Arc, Area, Drawing, Line
from brunelleschi.gui.document import Document

POCHE = QColor("#a6a6a6")
HIGHLIGHT = QColor("#1f6fd1")
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


class PlanView(QWidget):
    """Plan of one level. Wheel zooms at the cursor, dragging pans, ``fit`` frames all."""

    def __init__(self, document: Document) -> None:
        super().__init__()
        self.document = document
        self.level_id: UUID | None = None
        self.drawing = Drawing(())
        self.revision = 0  # increases every time the drawing is rebuilt (for tests)
        self._scale = 50.0  # pixels per metre
        self._centre = (0.0, 0.0)  # model point at the widget centre
        self._drag: QPointF | None = None
        self._fitted = False
        self.setMinimumSize(320, 240)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background: white")
        document.changed.connect(self.rebuild)
        document.selection_changed.connect(self.update)

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
            self._centre, self._scale = (0.0, 0.0), 50.0
        else:
            x0, y0, x1, y1 = extent
            w = max(x1 - x0, 1.0)
            h = max(y1 - y0, 1.0)
            avail_w = max(self.width() - 2 * MARGIN_PX, 50)
            avail_h = max(self.height() - 2 * MARGIN_PX, 50)
            self._scale = min(avail_w / w, avail_h / h)
            self._centre = ((x0 + x1) / 2, (y0 + y1) / 2)
        self._fitted = True
        self.update()

    def transform(self) -> QTransform:
        """Model metres (y up) to widget pixels (y down)."""
        t = QTransform()
        t.translate(self.width() / 2, self.height() / 2)
        t.scale(self._scale, -self._scale)
        t.translate(-self._centre[0], -self._centre[1])
        return t

    def to_model(self, point: QPointF) -> tuple[float, float]:
        inverted, _ = self.transform().inverted()
        p = inverted.map(point)
        return (p.x(), p.y())

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.2 ** (event.angleDelta().y() / 120)
        before = self.to_model(event.position())
        self._scale = min(max(self._scale * factor, 0.5), 5000.0)
        after = self.to_model(event.position())
        self._centre = (
            self._centre[0] + before[0] - after[0],
            self._centre[1] + before[1] - after[1],
        )
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._drag = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag is None:
            return
        delta = event.position() - self._drag
        self._drag = event.position()
        self._centre = (
            self._centre[0] - delta.x() / self._scale,
            self._centre[1] + delta.y() / self._scale,
        )
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag = None

    def resizeEvent(self, event: object) -> None:
        if not self._fitted:
            self.fit()

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
            painter.setPen(self._pen(QColor("black"), width, dashed))
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
        painter.setPen(self._pen(HIGHLIGHT, 3.0, False))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in outline]))

    @staticmethod
    def _pen(colour: QColor, width: float, dashed: bool) -> QPen:
        pen = QPen(colour, width)
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        if dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        return pen

    def visible_rect(self) -> QRectF:
        """The model area currently on screen (for tests and future tools)."""
        inverted, _ = self.transform().inverted()
        return inverted.mapRect(QRectF(self.rect()))
