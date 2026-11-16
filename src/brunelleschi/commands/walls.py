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
    with transaction(project):
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
    with transaction(project):
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
    """Delete a wall."""
    with transaction(project):
        wall = project.wall(ref)
        return project._remove_wall(wall.id)
