"""SVG writer for drawings, at a scale on an ISO paper sheet.

The SVG's ``width`` and ``height`` are the sheet in millimetres and its ``viewBox`` uses
millimetres too, so one user unit is one millimetre on paper and the file prints at the
stated scale. The drawing is centred on the sheet. Output is deterministic: fixed number
formatting, layers in a fixed order, elements in model order, no timestamps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from xml.sax.saxutils import escape, quoteattr

from brunelleschi.drawings.primitives import LAYERS, Arc, Area, Drawing, Line, Text, Vec
from brunelleschi.errors import DrawingError

# ISO 216 A sizes, portrait (width, height) in millimetres.
PAPER_SIZES: dict[str, tuple[int, int]] = {
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
    "A1": (594, 841),
    "A0": (841, 1189),
}
MARGIN = 10.0  # mm on each side, kept free of the drawing
TITLE_SIZE = 3.5  # mm, text height of the title line


@dataclass(frozen=True, slots=True)
class Sheet:
    """A sheet of paper and the scale a drawing is plotted at (1:``scale``)."""

    paper: str = "A3"
    portrait: bool = False
    scale: float = 50.0

    def size(self) -> tuple[float, float]:
        try:
            w, h = PAPER_SIZES[self.paper.upper()]
        except KeyError:
            names = ", ".join(PAPER_SIZES)
            raise DrawingError(f"unknown paper size {self.paper!r} (use {names})") from None
        return (float(w), float(h)) if self.portrait else (float(h), float(w))

    @property
    def label(self) -> str:
        orientation = "portrait" if self.portrait else "landscape"
        return f"{self.paper.upper()} {orientation}"


def _n(value: float) -> str:
    """Millimetres with micrometre precision, without trailing zeros; never ``-0``."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


class _Plotter:
    def __init__(self, drawing: Drawing, sheet: Sheet) -> None:
        if not (math.isfinite(sheet.scale) and sheet.scale > 0):
            raise DrawingError(f"the scale must be a positive number, not {sheet.scale!r}")
        self.width, self.height = sheet.size()
        self.k = 1000.0 / sheet.scale  # paper millimetres per model metre
        extent = drawing.extent()
        if extent is None:
            self.cx = self.cy = 0.0
            return
        x0, y0, x1, y1 = extent
        w, h = (x1 - x0) * self.k, (y1 - y0) * self.k
        room_w, room_h = self.width - 2 * MARGIN, self.height - 2 * MARGIN
        if w > room_w + 1e-9 or h > room_h + 1e-9:
            raise DrawingError(
                f"at 1:{sheet.scale:g} the drawing is {w:.0f} x {h:.0f} mm and does not fit "
                f"on {sheet.label} ({room_w:.0f} x {room_h:.0f} mm inside the margins); "
                "use a larger paper or a smaller scale"
            )
        self.cx, self.cy = (x0 + x1) / 2, (y0 + y1) / 2

    def xy(self, p: Vec) -> tuple[float, float]:
        return (
            self.width / 2 + (p[0] - self.cx) * self.k,
            self.height / 2 - (p[1] - self.cy) * self.k,
        )

    def pt(self, p: Vec) -> str:
        x, y = self.xy(p)
        return f"{_n(x)} {_n(y)}"


def _path(plotter: _Plotter, primitive: Area | Line | Arc) -> str:
    if isinstance(primitive, Area):
        parts = []
        for ring in primitive.rings:
            parts.append("M" + " L".join(plotter.pt(p) for p in ring) + " Z")
        return " ".join(parts)
    if isinstance(primitive, Line):
        d = "M" + " L".join(plotter.pt(p) for p in primitive.points)
        return d + " Z" if primitive.closed else d
    c, s, e = (plotter.xy(p) for p in (primitive.centre, primitive.start, primitive.end))
    radius = math.hypot(s[0] - c[0], s[1] - c[1])
    # In SVG's y-down coordinates a positive cross product is the positive-angle sweep.
    sweep = 1 if (s[0] - c[0]) * (e[1] - c[1]) - (s[1] - c[1]) * (e[0] - c[0]) > 0 else 0
    return f"M{_n(s[0])} {_n(s[1])} A{_n(radius)} {_n(radius)} 0 0 {sweep} {_n(e[0])} {_n(e[1])}"


def _style() -> str:
    rules = []
    for layer in LAYERS:
        if layer.name == "text":
            rules.append(".text{font-family:sans-serif;fill:#000000;stroke:none}")
            continue
        stroke = "stroke:none" if layer.stroke_width == 0 else "stroke:#000000"
        parts = [
            f"fill:{layer.fill or 'none'}",
            stroke,
            f"stroke-width:{_n(layer.stroke_width)}",
            "stroke-linejoin:miter",
            "stroke-linecap:butt",
        ]
        if layer.dashed:
            parts.append("stroke-dasharray:1.5 1")
        rules.append(f".{layer.name}{{{';'.join(parts)}}}")
    return "\n".join(rules)


def to_svg(drawing: Drawing, sheet: Sheet, title: str = "") -> str:
    """The drawing as an SVG document plotted on ``sheet``."""
    plotter = _Plotter(drawing, sheet)
    w, h = plotter.width, plotter.height
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{_n(w)}mm" '
        f'height="{_n(h)}mm" viewBox="0 0 {_n(w)} {_n(h)}">',
        f"<title>{escape(title)}</title>",
        f"<style>\n{_style()}\n</style>",
        f'<rect x="0" y="0" width="{_n(w)}" height="{_n(h)}" fill="#ffffff"/>',
    ]
    texts = list(drawing.texts)
    if title:
        texts.append(Text("text", (MARGIN, MARGIN / 2), title, TITLE_SIZE))
    for layer in LAYERS:
        items = [p for p in drawing.primitives if p.layer == layer.name]
        layer_texts = [t for t in texts if t.layer == layer.name]
        if not items and not layer_texts:
            continue
        out.append(f'<g id="{layer.name}" class="{layer.name}">')
        for p in items:
            rule = ' fill-rule="evenodd"' if isinstance(p, Area) else ""
            element = f" data-element={quoteattr(str(p.element))}" if p.element else ""
            out.append(f'<path d="{_path(plotter, p)}"{rule}{element}/>')
        for t in layer_texts:
            x, y = t.position[0], h - t.position[1]  # texts are placed from the bottom left
            out.append(
                f'<text x="{_n(x)}" y="{_n(y)}" font-size="{_n(t.size)}">{escape(t.text)}</text>'
            )
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"
