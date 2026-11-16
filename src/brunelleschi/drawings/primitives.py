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


Shape = Area | Line | Arc


@dataclass(frozen=True, slots=True)
class Block:
    """A named symbol in its own coordinates (metres), drawn wherever it is inserted.

    Doors and windows are blocks, so a DXF keeps them as reusable blocks (INSERT entities)
    while SVG and the screen draw their expanded shapes. Same name, same content.
    """

    name: str
    shapes: tuple[Shape, ...]


@dataclass(frozen=True, slots=True)
class Insert:
    """A block placed at ``position``, turned by ``rotation`` (radians, counter-clockwise),
    after mirroring its y axis if ``mirror``."""

    layer: str
    block: Block
    position: Vec
    rotation: float
    mirror: bool = False
    element: UUID | None = None

    def to_world(self, p: Vec) -> Vec:
        x, y = p[0], -p[1] if self.mirror else p[1]
        c, s = math.cos(self.rotation), math.sin(self.rotation)
        return (self.position[0] + c * x - s * y, self.position[1] + s * x + c * y)

    def expand(self) -> list[Shape]:
        """The block's shapes in model coordinates, carrying this insert's element."""
        out: list[Shape] = []
        for shape in self.block.shapes:
            if isinstance(shape, Line):
                points = tuple(self.to_world(p) for p in shape.points)
                out.append(Line(shape.layer, points, shape.closed, self.element))
            elif isinstance(shape, Arc):
                out.append(
                    Arc(
                        shape.layer,
                        self.to_world(shape.centre),
                        self.to_world(shape.start),
                        self.to_world(shape.end),
                        self.element,
                    )
                )
            else:
                rings = tuple(tuple(self.to_world(p) for p in ring) for ring in shape.rings)
                out.append(Area(shape.layer, rings, self.element))
        return out


Primitive = Area | Line | Arc | Insert


@dataclass(frozen=True, slots=True)
class Drawing:
    """A view's primitives in model coordinates, plus texts placed on the paper."""

    primitives: tuple[Primitive, ...]
    texts: tuple[Text, ...] = ()

    def flat(self) -> list[Shape]:
        """Every shape in model coordinates, with blocks expanded, in drawing order."""
        out: list[Shape] = []
        for p in self.primitives:
            out.extend(p.expand() if isinstance(p, Insert) else [p])
        return out

    def extent(self) -> tuple[float, float, float, float] | None:
        """(min x, min y, max x, max y) of every primitive, or None if empty."""
        xs: list[float] = []
        ys: list[float] = []
        for p in self.flat():
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
