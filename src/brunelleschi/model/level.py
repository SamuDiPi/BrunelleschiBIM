"""Levels: named horizontal datums that other elements are bound to."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class Level:
    """A named elevation, in metres, measured from the project zero."""

    id: UUID
    name: str
    elevation: float
