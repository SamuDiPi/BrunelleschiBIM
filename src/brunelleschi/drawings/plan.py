"""The plan view of a level: a horizontal cut, looking down.

What is drawn, for a cut ``cut_height`` above the level:

- walls the cut plane crosses: their outline at that height, joins and the voids of the
  openings the plane crosses included, filled (poché);
- walls of the level lower than the cut plane: their outline, thin (seen from above);
- doors cut by the plane: the leaf open at 90 degrees towards the swing side, hinged at
  the chosen jamb, and the swing arc;
- windows cut by the plane: the two wall faces and the glass line across the opening;
- openings entirely above the cut plane, in cut walls: their outline, dashed.
"""

from __future__ import annotations

import math
from uuid import UUID

from shapely import MultiPolygon, Polygon, unary_union
from shapely.geometry.polygon import orient

from brunelleschi.drawings.primitives import (
    Arc,
    Area,
    Block,
    Drawing,
    Insert,
    Line,
    Primitive,
    Vec,
)
from brunelleschi.geometry.joins import WallLine
from brunelleschi.model import LENGTH_TOLERANCE, Door, Jamb, Project, Side
from brunelleschi.regen import wall_geometry

DEFAULT_CUT_HEIGHT = 1.20


def _world(line: WallLine, x: float, y: float) -> Vec:
    """A point given along (x) and to the left of (y) a wall's centre line."""
    (sx, sy), (dx, dy) = line.start, line.direction
    return (sx + dx * x - dy * y, sy + dy * x + dx * y)


def _rings(polygon: Polygon) -> tuple[tuple[Vec, ...], ...]:
    # Counter-clockwise outer ring, clockwise holes, without the repeated closing point:
    # a fixed convention keeps the output stable.
    p = orient(polygon, 1.0)
    rings = [p.exterior, *p.interiors]
    return tuple(tuple((float(x), float(y)) for x, y in ring.coords[:-1]) for ring in rings)


def _mm(value: float) -> int:
    return round(value * 1000)


def door_block(width: float) -> Block:
    """A door of ``width``: hinge at the origin, the leaf open along +y, its swing arc down
    to the closed position on +x."""
    return Block(
        f"DOOR_{_mm(width)}",
        (
            Line("door", ((0.0, 0.0), (0.0, width))),
            Arc("door-swing", (0.0, 0.0), (0.0, width), (width, 0.0)),
        ),
    )


def window_block(width: float, wall_thickness: float) -> Block:
    """A window of ``width`` in a wall of ``wall_thickness``, centred on the origin, the
    wall along x: the two wall faces and the glass line."""
    half_w, half_t = width / 2, wall_thickness / 2
    return Block(
        f"WINDOW_{_mm(width)}x{_mm(wall_thickness)}",
        tuple(Line("window", ((-half_w, y), (half_w, y))) for y in (half_t, 0.0, -half_t)),
    )


def plan_view(
    project: Project, level: UUID | str, cut_height: float = DEFAULT_CUT_HEIGHT
) -> Drawing:
    """The plan of ``level`` (its id or name) cut ``cut_height`` metres above it."""
    lv = project.level(level)
    z = lv.elevation + cut_height
    geometry = wall_geometry(project)
    cut = geometry.plan_cut(z)
    primitives: list[Primitive] = []

    cut_parts: list[Polygon] = []
    for wall in project.walls:
        line = geometry.lines[wall.id]
        shape = cut.get(wall.id)
        if shape is not None:
            cut_parts.extend(shape.geoms if isinstance(shape, MultiPolygon) else [shape])
        elif line.base_z < z and lv.elevation + LENGTH_TOLERANCE < line.top_z <= z:
            corners = geometry.footprints[wall.id].corners
            primitives.append(Line("wall-projection", tuple(corners), True, wall.id))

    # Joined walls read as one mass: fill and outline their union, not each wall. Filling
    # walls one by one leaves visible seams along the joins in most renderers.
    merged = unary_union(cut_parts)
    pieces = merged.geoms if isinstance(merged, MultiPolygon) else [merged]
    for piece in sorted(pieces, key=lambda g: g.bounds):
        if isinstance(piece, Polygon) and not piece.is_empty:
            rings = _rings(piece)
            primitives.append(Area("wall-cut", rings))
            for ring in rings:
                primitives.append(Line("wall-cut-outline", ring, True))

    for element in project.hosted:
        if element.host_id not in cut:
            continue
        line = geometry.lines[element.host_id]
        o = geometry.openings[element.id]
        a, b = element.along()
        half = line.half
        if o.spans(z):
            dx, dy = line.direction
            if isinstance(element, Door):
                s = 1.0 if element.swing_side == Side.LEFT else -1.0
                start_hinge = element.hinge == Jamb.START
                h = a if start_hinge else b
                # Block axes: x from the hinge towards the other jamb, y into the swing.
                x_dir = (dx, dy) if start_hinge else (-dx, -dy)
                y_dir = (-dy * s, dx * s)
                mirror = x_dir[0] * y_dir[1] - x_dir[1] * y_dir[0] < 0
                primitives.append(
                    Insert(
                        "door",
                        door_block(element.width),
                        _world(line, h, s * half),
                        math.atan2(x_dir[1], x_dir[0]),
                        mirror,
                        element.id,
                    )
                )
            else:
                primitives.append(
                    Insert(
                        "window",
                        window_block(element.width, line.thickness),
                        _world(line, (a + b) / 2, 0.0),
                        math.atan2(dy, dx),
                        False,
                        element.id,
                    )
                )
        elif o.z_bottom >= z:
            primitives.append(Line("opening-above", o.corners, True, element.id))

    return Drawing(tuple(primitives))
