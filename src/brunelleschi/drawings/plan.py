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

from uuid import UUID

from shapely import MultiPolygon, Polygon, unary_union
from shapely.geometry.polygon import orient

from brunelleschi.drawings.primitives import Arc, Area, Drawing, Line, Primitive, Vec
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
            if isinstance(element, Door):
                s = 1.0 if element.swing_side == Side.LEFT else -1.0
                h, other = (a, b) if element.hinge == Jamb.START else (b, a)
                hinge = _world(line, h, s * half)
                tip = _world(line, h, s * (half + element.width))
                closed = _world(line, other, s * half)
                primitives.append(Line("door", (hinge, tip), False, element.id))
                primitives.append(Arc("door-swing", hinge, tip, closed, element.id))
            else:
                for y in (half, 0.0, -half):
                    points = (_world(line, a, y), _world(line, b, y))
                    primitives.append(Line("window", points, False, element.id))
        elif o.z_bottom >= z:
            primitives.append(Line("opening-above", o.corners, True, element.id))

    return Drawing(tuple(primitives))
