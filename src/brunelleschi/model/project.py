"""The project: the container of every element and the place where invariants are checked."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from uuid import UUID

from brunelleschi.errors import ModelError, NotFoundError
from brunelleschi.model.level import Level
from brunelleschi.model.units import MAX_ABS_COORDINATE, is_valid_length

MAX_NAME_LENGTH = 200


def normalize_name(name: str) -> str:
    """Names are compared without surrounding spaces and without case."""
    return name.strip().casefold()


@dataclass(slots=True)
class Project:
    """All the elements of one building project.

    Elements keep the order in which they were created, which makes saved files stable.
    Mutating methods are for ``brunelleschi.commands`` only; other code reads.
    """

    name: str
    _levels: dict[UUID, Level] = field(default_factory=dict)

    # ------------------------------------------------------------------ queries

    @property
    def levels(self) -> list[Level]:
        """Levels in creation order."""
        return list(self._levels.values())

    def levels_by_elevation(self) -> list[Level]:
        """Levels from the lowest to the highest (name breaks ties, for a stable order)."""
        return sorted(self._levels.values(), key=lambda lv: (lv.elevation, lv.name.casefold()))

    def level(self, ref: UUID | str) -> Level:
        """A level by id, or by name (ignoring case and surrounding spaces)."""
        if isinstance(ref, UUID):
            try:
                return self._levels[ref]
            except KeyError:
                raise NotFoundError(f"no level with id {ref}") from None
        wanted = normalize_name(ref)
        for level in self._levels.values():
            if normalize_name(level.name) == wanted:
                return level
        raise NotFoundError(f"no level named {ref!r}")

    def __iter__(self) -> Iterator[Level]:
        return iter(self._levels.values())

    # --------------------------------------------------------------- mutations

    def _add_level(self, level: Level) -> None:
        if level.id in self._levels:
            raise ModelError(f"a level with id {level.id} already exists")
        self._levels[level.id] = level

    def _remove_level(self, level_id: UUID) -> Level:
        try:
            return self._levels.pop(level_id)
        except KeyError:
            raise NotFoundError(f"no level with id {level_id}") from None

    # --------------------------------------------------------------- invariants

    def check(self) -> None:
        """Raise ``ModelError`` describing every broken invariant, or return silently."""
        problems: list[str] = []
        if not self.name.strip():
            problems.append("the project name is empty")
        seen: dict[str, Level] = {}
        for level in self._levels.values():
            label = f"level {level.name!r}"
            if not level.name.strip():
                problems.append(f"level {level.id} has an empty name")
                label = f"level {level.id}"
            elif len(level.name) > MAX_NAME_LENGTH:
                problems.append(f"{label}: name longer than {MAX_NAME_LENGTH} characters")
            if not is_valid_length(level.elevation):
                problems.append(
                    f"{label}: elevation must be a finite number of metres within "
                    f"±{MAX_ABS_COORDINATE:g}"
                )
            key = normalize_name(level.name)
            if key and key in seen:
                problems.append(
                    f"level name {level.name!r} clashes with {seen[key].name!r} "
                    "(names must be unique, ignoring case)"
                )
            seen.setdefault(key, level)
        if problems:
            raise ModelError("; ".join(problems))
