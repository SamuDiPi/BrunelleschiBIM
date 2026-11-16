"""Render an SVG to PNG, to look at drawings without opening a viewer.

Uses QtSvg from PySide6, which is not a dependency of the project; run it in a throwaway
environment:

    uv run --isolated --no-project --with PySide6-Essentials python tools/render_svg.py \\
        plan.svg plan.png [pixels_per_mm]

It draws into an image in memory and opens no window. Do not set QT_QPA_PLATFORM to
"offscreen" or "minimal" on Windows: those platforms find no fonts and drop all text.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        return 2
    _app = QGuiApplication(sys.argv[:1])
    renderer = QSvgRenderer(sys.argv[1])
    if not renderer.isValid():
        print(f"not a valid SVG: {sys.argv[1]}", file=sys.stderr)
        return 1
    k = float(sys.argv[3]) if len(sys.argv) == 4 else 4.0
    # Size from the sheet the SVG declares (width/height, read by Qt at 96 dpi), not from
    # its viewBox, whose units are the writer's own choice.
    size = renderer.defaultSize()
    width_mm, height_mm = size.width() * 25.4 / 96, size.height() * 25.4 / 96
    image = QImage(int(width_mm * k), int(height_mm * k), QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, image.width(), image.height()))
    painter.end()
    image.save(sys.argv[2])
    print(f"wrote {sys.argv[2]} ({image.width()} x {image.height()} px)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
