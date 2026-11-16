"""The 3D view: a read-only, shaded model that follows every change (ADR 0008).

Mouse: left drag orbits, right or middle drag pans, the wheel zooms, a left click selects
(the selection is shared with the plan and the browser); F frames the model.
"""

from __future__ import annotations

import math
from uuid import UUID

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from brunelleschi.gui.camera import OrbitCamera
from brunelleschi.gui.document import Document
from brunelleschi.gui.renderer import Renderer, surface_format
from brunelleschi.gui.scene3d import Scene, build_scene

CLICK_PX = 4
ORBIT_DEG_PER_PX = 0.4


class Viewport3D(QOpenGLWidget):
    def __init__(self, document: Document) -> None:
        super().__init__()
        self.setFormat(surface_format())
        self.document = document
        self.camera = OrbitCamera.default()
        self.scene = Scene()
        self.renderer = Renderer()
        self.revision = 0  # increases at every scene rebuild (for tests)
        self._uploaded = -1
        self._fitted = False
        self._press: QPointF | None = None
        self._last: QPointF | None = None
        self._button = Qt.MouseButton.NoButton
        self.unavailable: str | None = None
        self.setMinimumSize(240, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        document.changed.connect(self.rebuild)
        document.selection_changed.connect(self.update)
        self.rebuild()

    # ------------------------------------------------------------ model

    def rebuild(self) -> None:
        self.scene = build_scene(self.document.project)
        self.revision += 1
        if not self._fitted:
            self.fit()
        self.update()

    def fit(self) -> None:
        bounds = self.scene.bounds()
        if bounds is not None:
            self.camera.fit(*bounds)
            self._fitted = True
        self.update()

    # ---------------------------------------------------------- OpenGL

    def initializeGL(self) -> None:
        if not self.renderer.initialize():
            self.unavailable = self.renderer.error or "OpenGL 3.3 is not available"

    def paintGL(self) -> None:
        if self.unavailable:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#f6f6f4"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "3D view unavailable:\n" + self.unavailable,
            )
            painter.end()
            return
        if self._uploaded != self.revision:
            self.renderer.upload(self.scene)
            self._uploaded = self.revision
        ratio = self.devicePixelRatioF()
        width, height = int(self.width() * ratio), int(self.height() * ratio)
        selected = self.scene.index_of(self.document.selected)
        self.renderer.draw(self.camera.matrix(width, height), width, height, selected)

    # ------------------------------------------------------------ input

    def pick_at(self, x: float, y: float) -> UUID | None:
        """The element under a widget point, or None (works without OpenGL)."""
        origin, direction = self.camera.ray(x, y, max(self.width(), 1), max(self.height(), 1))
        return self.scene.pick(origin, direction)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._press = self._last = event.position()
        self._button = event.button()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._last is None:
            return
        delta = event.position() - self._last
        self._last = event.position()
        if self._button == Qt.MouseButton.LeftButton:
            self.camera.orbit(-delta.x() * ORBIT_DEG_PER_PX, delta.y() * ORBIT_DEG_PER_PX)
        else:
            self.camera.pan(delta.x(), delta.y(), self.height())
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._press is not None and self._button == Qt.MouseButton.LeftButton:
            moved = event.position() - self._press
            if math.hypot(moved.x(), moved.y()) < CLICK_PX:
                picked = self.pick_at(event.position().x(), event.position().y())
                self.document.select(picked)
        self._press = self._last = None
        self._button = Qt.MouseButton.NoButton

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.camera.zoom(0.85 ** (event.angleDelta().y() / 120))
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_F:
            self.fit()
        else:
            super().keyPressEvent(event)
