"""Snapping and picking in the plan: pure functions of model coordinates, no Qt.

Snaps, by priority:

1. ``endpoint``: a wall end within the tolerance;
2. ``on wall``: the closest point on a wall's centre line within the tolerance (a wall
   drawn to it forms a T join, which needs its end exactly on that line);
3. ``grid``: the nearest grid point.

With ``ortho``, the point is first constrained to the horizontal or vertical through the
anchor (the previous point); an endpoint snap still wins, because joining walls matters
more than a perfect axis. Tolerances are in metres: the view converts pixels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from brunelleschi import api

Vec = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Snap:
    point: Vec
    kind: str  # "endpoint", "on wall", "grid", "ortho" or "free"
    wall: UUID | None = None


def _closest_on_segment(p: Vec, a: Vec, b: Vec) -> tuple[Vec, float]:
    """The closest point to ``p`` on segment ``ab`` and its distance along it (0..length)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return a, 0.0
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return (a[0] + t * dx, a[1] + t * dy), t * math.sqrt(length2)


def _ortho(point: Vec, anchor: Vec) -> Vec:
    if abs(point[0] - anchor[0]) >= abs(point[1] - anchor[1]):
        return (point[0], anchor[1])
    return (anchor[0], point[1])


def snap(
    project: api.Project,
    point: Vec,
    *,
    tolerance: float,
    grid: float | None = 0.10,
    anchor: Vec | None = None,
    ortho: bool = False,
    exclude: frozenset[UUID] = frozenset(),
) -> Snap:
    """Where a click at ``point`` lands. ``exclude`` skips walls being edited."""
    walls = [w for w in project.walls if w.id not in exclude]

    best: tuple[float, Snap] | None = None
    for w in walls:
        for end in (w.start, w.end):
            d = math.hypot(point[0] - end.x, point[1] - end.y)
            if d <= tolerance and (best is None or d < best[0]):
                best = (d, Snap((end.x, end.y), "endpoint", w.id))
    if best is not None:
        return best[1]

    constrained = _ortho(point, anchor) if ortho and anchor is not None else point
    # On a wall, keep the position along it on the grid: project the nearest grid point,
    # not the cursor, whose position is only as precise as a screen pixel.
    gridded = (
        (round(constrained[0] / grid) * grid, round(constrained[1] / grid) * grid)
        if grid
        else constrained
    )
    for w in walls:
        a, b = (w.start.x, w.start.y), (w.end.x, w.end.y)
        near, _ = _closest_on_segment(constrained, a, b)
        d = math.hypot(constrained[0] - near[0], constrained[1] - near[1])
        if d <= tolerance and (best is None or d < best[0]):
            foot, _ = _closest_on_segment(gridded, a, b)
            if ortho and anchor is not None:
                foot = _ortho_on_wall(foot, anchor, w) or foot
            best = (d, Snap((round(foot[0], 9), round(foot[1], 9)), "on wall", w.id))
    if best is not None:
        return best[1]

    if grid:
        gx = round(constrained[0] / grid) * grid
        gy = round(constrained[1] / grid) * grid
        if ortho and anchor is not None:
            gx, gy = (gx, anchor[1]) if constrained[1] == anchor[1] else (anchor[0], gy)
        return Snap((round(gx, 9), round(gy, 9)), "grid")
    return Snap(constrained, "ortho" if ortho and anchor is not None else "free")


def _ortho_on_wall(foot: Vec, anchor: Vec, wall: api.Wall) -> Vec | None:
    """Where the horizontal or vertical through the anchor crosses the wall, if it does."""
    (ax, ay), (sx, sy), (ex, ey) = anchor, (wall.start.x, wall.start.y), (wall.end.x, wall.end.y)
    horizontal = abs(foot[1] - ay) < abs(foot[0] - ax)
    if horizontal and ey != sy:
        t = (ay - sy) / (ey - sy)
        return (sx + t * (ex - sx), ay) if 0 <= t <= 1 else None
    if not horizontal and ex != sx:
        t = (ax - sx) / (ex - sx)
        return (ax, sy + t * (ey - sy)) if 0 <= t <= 1 else None
    return None


# ---------------------------------------------------------------- picking


def _inside(point: Vec, polygon: tuple[Vec, ...]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def pick(project: api.Project, point: Vec, *, tolerance: float, level: UUID | None) -> UUID | None:
    """The element under ``point`` on the plan of ``level``: doors and windows first, then
    walls (inside the outline, or within the tolerance of the centre line), else None."""
    geometry = api.wall_geometry(project)
    on_level = {w.id for w in project.walls if level is None or w.base_level_id == level}
    for element in project.hosted:
        if element.host_id in on_level and _inside(point, geometry.openings[element.id].corners):
            return element.id
    best: tuple[float, UUID] | None = None
    for wall in project.walls:
        if wall.id not in on_level:
            continue
        if _inside(point, geometry.footprints[wall.id].corners):
            return wall.id
        foot, _ = _closest_on_segment(point, (wall.start.x, wall.start.y), (wall.end.x, wall.end.y))
        d = math.hypot(point[0] - foot[0], point[1] - foot[1])
        if d <= tolerance + wall.thickness / 2 and (best is None or d < best[0]):
            best = (d, wall.id)
    return best[1] if best else None


def along_wall(wall: api.Wall, point: Vec) -> tuple[float, str]:
    """Distance of the point's projection from the wall's start, and the side it is on
    (``"left"`` or ``"right"``, seen from the start)."""
    a, b = (wall.start.x, wall.start.y), (wall.end.x, wall.end.y)
    _, distance = _closest_on_segment(point, a, b)
    cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])
    return distance, "left" if cross >= 0 else "right"


def grip_at(wall: api.Wall, point: Vec, tolerance: float) -> str | None:
    """``"start"`` or ``"end"`` if the point is on that end's grip."""
    for end, p in (("start", wall.start), ("end", wall.end)):
        if math.hypot(point[0] - p.x, point[1] - p.y) <= tolerance:
            return end
    return None
