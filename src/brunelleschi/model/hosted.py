"""Doors and windows: elements hosted in a wall, placed by distance along it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Side(StrEnum):
    """A side of a wall, seen from its start looking towards its end."""

    LEFT = "left"
    RIGHT = "right"


class Jamb(StrEnum):
    """One of the two jambs of an opening: the one nearer the wall's start or its end."""

    START = "start"
    END = "end"


@dataclass(slots=True)
class HostedElement:
    """An element placed in a host wall.

    ``position`` is the distance from the wall's start to the element's centre, along the
    centre line, so resizing keeps the element centred. ``sill_height`` is measured from
    the wall's base. The element's position in space is derived from its wall: moving or
    raising the wall moves it.
    """

    id: UUID
    host_id: UUID
    position: float
    width: float
    height: float
    sill_height: float

    @property
    def kind(self) -> str:
        return type(self).__name__.lower()

    def along(self) -> tuple[float, float]:
        """Start and end of the element along the host's centre line."""
        return self.position - self.width / 2, self.position + self.width / 2

    def vertical(self) -> tuple[float, float]:
        """Bottom and top of the element above the host's base."""
        return self.sill_height, self.sill_height + self.height


@dataclass(slots=True)
class Door(HostedElement):
    """A door. It swings to ``swing_side`` of the wall, hinged on the ``hinge`` jamb."""

    swing_side: Side = Side.LEFT
    hinge: Jamb = Jamb.START


@dataclass(slots=True)
class Window(HostedElement):
    """A window."""
