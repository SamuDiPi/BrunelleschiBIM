"""Commands on levels."""

from __future__ import annotations

import math
from uuid import UUID, uuid4

from brunelleschi.commands.transaction import transaction
from brunelleschi.errors import ModelError
from brunelleschi.model import Level, Project


def _dependents(project: Project, level: Level) -> list[str]:
    """Descriptions of the elements bound to a level.

    No element can reference a level yet; walls do from milestone M2. The hook exists
    now so that deleting a level is already guarded in one place.
    """
    del project, level
    return []


def add_level(
    project: Project, name: str, elevation: float, *, level_id: UUID | None = None
) -> Level:
    """Create a level. Names must be unique (ignoring case); elevations are in metres."""
    level = Level(id=level_id or uuid4(), name=name.strip(), elevation=float(elevation))
    with transaction(project):
        project._add_level(level)
    return level


def rename_level(project: Project, ref: UUID | str, new_name: str) -> Level:
    """Give a level a new name."""
    with transaction(project):
        level = project.level(ref)
        level.name = new_name.strip()
    return project.level(level.id)


def set_level_elevation(project: Project, ref: UUID | str, elevation: float) -> Level:
    """Move a level to a new elevation, in metres.

    From milestone M2, elements bound to the level follow it.
    """
    if not math.isfinite(float(elevation)):
        raise ModelError("the elevation must be a finite number of metres")
    with transaction(project):
        level = project.level(ref)
        level.elevation = float(elevation)
    return project.level(level.id)


def delete_level(project: Project, ref: UUID | str) -> Level:
    """Delete a level. Refused while other elements are bound to it."""
    with transaction(project):
        level = project.level(ref)
        dependents = _dependents(project, level)
        if dependents:
            raise ModelError(
                f"level {level.name!r} cannot be deleted: it is used by " + ", ".join(dependents)
            )
        return project._remove_level(level.id)
