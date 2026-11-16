"""Commands on doors and windows."""

from __future__ import annotations

from uuid import UUID, uuid4

from brunelleschi.commands.transaction import transaction
from brunelleschi.errors import ModelError
from brunelleschi.model import Door, HostedElement, Jamb, Project, Side, Window


def _side(value: Side | str) -> Side:
    try:
        return Side(value)
    except ValueError:
        raise ModelError(f"swing side must be left or right, not {value!r}") from None


def _jamb(value: Jamb | str) -> Jamb:
    try:
        return Jamb(value)
    except ValueError:
        raise ModelError(f"hinge must be start or end, not {value!r}") from None


def add_door(
    project: Project,
    wall: UUID | str,
    position: float,
    width: float,
    height: float,
    *,
    sill_height: float = 0.0,
    swing_side: Side | str = Side.LEFT,
    hinge: Jamb | str = Jamb.START,
    door_id: UUID | None = None,
) -> Door:
    """Place a door in a wall, its centre ``position`` metres from the wall's start."""
    with transaction(project):
        door = Door(
            id=door_id or uuid4(),
            host_id=project.wall(wall).id,
            position=float(position),
            width=float(width),
            height=float(height),
            sill_height=float(sill_height),
            swing_side=_side(swing_side),
            hinge=_jamb(hinge),
        )
        project._add_hosted(door)
    return door


def add_window(
    project: Project,
    wall: UUID | str,
    position: float,
    width: float,
    height: float,
    sill_height: float,
    *,
    window_id: UUID | None = None,
) -> Window:
    """Place a window in a wall, its centre ``position`` metres from the wall's start and
    its sill ``sill_height`` metres above the wall's base."""
    with transaction(project):
        window = Window(
            id=window_id or uuid4(),
            host_id=project.wall(wall).id,
            position=float(position),
            width=float(width),
            height=float(height),
            sill_height=float(sill_height),
        )
        project._add_hosted(window)
    return window


def modify_hosted(
    project: Project,
    ref: UUID | str,
    *,
    wall: UUID | str | None = None,
    position: float | None = None,
    width: float | None = None,
    height: float | None = None,
    sill_height: float | None = None,
    swing_side: Side | str | None = None,
    hinge: Jamb | str | None = None,
) -> HostedElement:
    """Change some parameters of a door or window; ``None`` keeps a value. ``wall`` moves
    the element to another wall."""
    with transaction(project):
        element = project.hosted_element(ref)
        if wall is not None:
            element.host_id = project.wall(wall).id
        if position is not None:
            element.position = float(position)
        if width is not None:
            element.width = float(width)
        if height is not None:
            element.height = float(height)
        if sill_height is not None:
            element.sill_height = float(sill_height)
        if swing_side is not None or hinge is not None:
            if not isinstance(element, Door):
                raise ModelError(f"only doors have a swing side and a hinge, not a {element.kind}")
            if swing_side is not None:
                element.swing_side = _side(swing_side)
            if hinge is not None:
                element.hinge = _jamb(hinge)
    return element


def delete_hosted(project: Project, ref: UUID | str) -> HostedElement:
    """Delete a door or window."""
    with transaction(project):
        return project._remove_hosted(project.hosted_element(ref).id)
