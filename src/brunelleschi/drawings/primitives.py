"""Neutral 2D drawing primitives, in model coordinates (metres, y up).

Views produce these; writers (SVG now, DXF later) turn them into files. Every primitive
belongs to a layer, which decides how it is drawn (see ``LAYERS``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

Vec = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Layer:
    """How the primitives of a layer are drawn. Widths are pen widths on paper, in mm."""

    name: str
    stroke_width: float
    fill: str | None = None
    dashed: bool = False


# In drawing order: later layers are drawn on top.
LAYERS: tuple[Layer, ...] = (
    Layer("wall-projection", 0.18),
    Layer("wall-cut", 0.0, fill="#a6a6a6"),  # fill only: walls merge into one poche
    Layer("wall-cut-outline", 0.50),  # the outline of all cut walls together
    Layer("opening-above", 0.25, dashed=True),  # over the poche, so it stays visible
    Layer("window", 0.25),
    Layer("door", 0.35),
    Layer("door-swing", 0.18),
    Layer("text", 0.0),
)
LAYER_NAMES = tuple(layer.name for layer in LAYERS)


@dataclass(frozen=True, slots=True)
class Area:
    """A filled region: an outer ring and holes, each a closed list of points."""

    layer: str
    rings: tuple[tuple[Vec, ...], ...]
    element: UUID | None = None


@dataclass(frozen=True, slots=True)
class Line:
    """An open or closed polyline."""

    layer: str
    points: tuple[Vec, ...]
    closed: bool = False
    element: UUID | None = None


@dataclass(frozen=True, slots=True)
class Arc:
    """The minor circular arc from ``start`` to ``end`` around ``centre``."""

    layer: str
    centre: Vec
    start: Vec
    end: Vec
    element: UUID | None = None


@dataclass(frozen=True, slots=True)
class Text:
    """A line of text placed on the paper, in millimetres from its bottom-left corner."""

    layer: str
    position: Vec
    text: str
    size: float


Primitive = Area | Line | Arc


@dataclass(frozen=True, slots=True)
class Drawing:
    """A view's primitives in model coordinates, plus texts placed on the paper."""

    primitives: tuple[Primitive, ...]
    texts: tuple[Text, ...] = ()

    def extent(self) -> tuple[float, float, float, float] | None:
        """(min x, min y, max x, max y) of every primitive, or None if empty."""
        xs: list[float] = []
        ys: list[float] = []
        for p in self.primitives:
            if isinstance(p, Area):
                points = [pt for ring in p.rings for pt in ring]
            elif isinstance(p, Line):
                points = list(p.points)
            else:
                points = arc_extreme_points(p)
            xs.extend(pt[0] for pt in points)
            ys.extend(pt[1] for pt in points)
        if not xs:
            return None
        return min(xs), min(ys), max(xs), max(ys)


def arc_extreme_points(arc: Arc) -> list[Vec]:
    """The arc's ends and the points where it reaches furthest along x or y."""
    cx, cy = arc.centre
    a0 = math.atan2(arc.start[1] - cy, arc.start[0] - cx)
    a1 = math.atan2(arc.end[1] - cy, arc.end[0] - cx)
    sweep = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi  # the minor arc, signed
    r = math.hypot(arc.start[0] - cx, arc.start[1] - cy)
    points = [arc.start, arc.end]
    for k in range(4):
        angle = k * math.pi / 2
        offset = (angle - a0) % (2 * math.pi)
        if (sweep >= 0 and offset < sweep) or (sweep < 0 and offset - 2 * math.pi > sweep):
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points
