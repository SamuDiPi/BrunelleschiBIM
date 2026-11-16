"""Walls: straight, bound to levels at their base and, optionally, at their top."""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Point:
    """A point in plan, in metres."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class TopAtLevel:
    """The wall top follows a level, plus an offset (positive is up)."""

    level_id: UUID
    offset: float = 0.0


@dataclass(frozen=True, slots=True)
class UnconnectedHeight:
    """The wall top is a fixed height above the wall base."""

    height: float


WallTop = TopAtLevel | UnconnectedHeight


@dataclass(slots=True)
class Wall:
    """A straight wall.

    ``start`` and ``end`` are the ends of the wall's centre line. The base is the base
    level's elevation plus ``base_offset``. Absolute elevations are never stored: they are
    derived from the levels, so moving a level moves every wall bound to it.
    """

    id: UUID
    start: Point
    end: Point
    thickness: float
    base_level_id: UUID
    base_offset: float
    top: WallTop

    @property
    def length(self) -> float:
        return math.hypot(self.end.x - self.start.x, self.end.y - self.start.y)

    def level_ids(self) -> set[UUID]:
        """The levels this wall is bound to."""
        ids = {self.base_level_id}
        if isinstance(self.top, TopAtLevel):
            ids.add(self.top.level_id)
        return ids
