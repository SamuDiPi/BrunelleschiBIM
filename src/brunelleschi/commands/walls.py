"""Commands on walls."""

from __future__ import annotations

from uuid import UUID, uuid4

from brunelleschi.commands.transaction import transaction
from brunelleschi.errors import ModelError
from brunelleschi.model import Point, Project, TopAtLevel, UnconnectedHeight, Wall, WallTop

PointLike = Point | tuple[float, float]
LevelRef = UUID | str


def _point(value: PointLike) -> Point:
    if isinstance(value, Point):
        return value
    x, y = value
    return Point(float(x), float(y))


def add_wall(
    project: Project,
    start: PointLike,
    end: PointLike,
    thickness: float,
    base_level: LevelRef,
    *,
    base_offset: float = 0.0,
    top_level: LevelRef | None = None,
    top_offset: float = 0.0,
    height: float | None = None,
    wall_id: UUID | None = None,
) -> Wall:
    """Create a straight wall from ``start`` to ``end`` (its centre line).

    The top is given either by ``top_level`` (plus ``top_offset``) or by an unconnected
    ``height`` above the base, not both.
    """
    if top_level is not None and height is not None:
        raise ModelError("give either a top level or a height, not both")
    with transaction(project, "Add wall"):
        top: WallTop
        if top_level is not None:
            top = TopAtLevel(project.level(top_level).id, float(top_offset))
        elif height is not None:
            if top_offset:
                raise ModelError("a top offset needs a top level")
            top = UnconnectedHeight(float(height))
        else:
            raise ModelError("give a top level or a height")
        wall = Wall(
            id=wall_id or uuid4(),
            start=_point(start),
            end=_point(end),
            thickness=float(thickness),
            base_level_id=project.level(base_level).id,
            base_offset=float(base_offset),
            top=top,
        )
        project._add_wall(wall)
    return wall


def modify_wall(
    project: Project,
    ref: UUID | str,
    *,
    start: PointLike | None = None,
    end: PointLike | None = None,
    thickness: float | None = None,
    base_level: LevelRef | None = None,
    base_offset: float | None = None,
    top_level: LevelRef | None = None,
    top_offset: float | None = None,
    height: float | None = None,
) -> Wall:
    """Change some parameters of a wall; parameters left as ``None`` keep their value.

    ``top_level`` binds the top to a level, ``height`` makes it unconnected; giving
    ``top_offset`` alone changes the offset of a wall whose top is already bound.
    """
    if top_level is not None and height is not None:
        raise ModelError("give either a top level or a height, not both")
    with transaction(project, "Modify wall"):
        wall = project.wall(ref)
        if start is not None:
            wall.start = _point(start)
        if end is not None:
            wall.end = _point(end)
        if thickness is not None:
            wall.thickness = float(thickness)
        if base_level is not None:
            wall.base_level_id = project.level(base_level).id
        if base_offset is not None:
            wall.base_offset = float(base_offset)
        if top_level is not None:
            if top_offset is None:
                top_offset = wall.top.offset if isinstance(wall.top, TopAtLevel) else 0.0
            wall.top = TopAtLevel(project.level(top_level).id, float(top_offset))
        elif height is not None:
            if top_offset is not None:
                raise ModelError("a top offset needs a top level")
            wall.top = UnconnectedHeight(float(height))
        elif top_offset is not None:
            if not isinstance(wall.top, TopAtLevel):
                raise ModelError("the wall top is not bound to a level, so it has no offset")
            wall.top = TopAtLevel(wall.top.level_id, float(top_offset))
    return wall


def delete_wall(project: Project, ref: UUID | str) -> Wall:
    """Delete a wall, together with its doors and windows."""
    with transaction(project, "Delete wall"):
        wall = project.wall(ref)
        for element in project.hosted_in(wall.id):
            project._remove_hosted(element.id)
        return project._remove_wall(wall.id)


def _same_point(a: Point, b: Point) -> bool:
    # The same rule as wall joins: equal on the micrometre grid.
    return round(a.x * 1e6) == round(b.x * 1e6) and round(a.y * 1e6) == round(b.y * 1e6)


def _set_end(project: Project, wall_id: UUID, end: str, point: Point) -> None:
    if end == "start":
        modify_wall(project, wall_id, start=point)
    else:
        modify_wall(project, wall_id, end=point)


def _ends_at(project: Project, point: Point, exclude: UUID) -> list[tuple[Wall, str]]:
    found = []
    for wall in project.walls:
        if wall.id == exclude:
            continue
        if _same_point(wall.start, point):
            found.append((wall, "start"))
        if _same_point(wall.end, point):
            found.append((wall, "end"))
    return found


def move_wall_end(
    project: Project,
    ref: UUID | str,
    end: str,
    to: PointLike,
    *,
    drag_joined: bool = True,
) -> Wall:
    """Move the ``"start"`` or ``"end"`` of a wall to a new point.

    With ``drag_joined`` (the default), the ends of other walls that met it there move too,
    so corners stay joined, as when dragging a corner in a CAD program.
    """
    if end not in ("start", "end"):
        raise ModelError(f"a wall end is 'start' or 'end', not {end!r}")
    target = _point(to)
    with transaction(project, "Move wall end"):
        wall = project.wall(ref)
        old = wall.start if end == "start" else wall.end
        followers = _ends_at(project, old, wall.id) if drag_joined else []
        _set_end(project, wall.id, end, target)
        for other, other_end in followers:
            _set_end(project, other.id, other_end, target)
    return wall


def move_wall(
    project: Project,
    ref: UUID | str,
    dx: float,
    dy: float,
    *,
    drag_joined: bool = True,
) -> Wall:
    """Move a wall by (dx, dy) metres, its doors and windows with it.

    With ``drag_joined`` (the default), walls joined to its ends stretch to follow.
    """
    with transaction(project, "Move wall"):
        wall = project.wall(ref)
        moves = [("start", wall.start), ("end", wall.end)]
        followers = (
            [(w, e, p) for _, p in moves for w, e in _ends_at(project, p, wall.id)]
            if drag_joined
            else []
        )
        new_start = Point(wall.start.x + dx, wall.start.y + dy)
        new_end = Point(wall.end.x + dx, wall.end.y + dy)
        modify_wall(project, wall.id, start=new_start, end=new_end)
        for other, other_end, old in followers:
            target = new_start if _same_point(old, moves[0][1]) else new_end
            _set_end(project, other.id, other_end, target)
    return wall
