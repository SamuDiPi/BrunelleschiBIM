"""The building model: elements, their parameters and the references between them.

This package depends on nothing else in ``brunelleschi`` except ``errors``. It holds data
and invariants; changes go through ``brunelleschi.commands``.
"""

from brunelleschi.model.level import Level
from brunelleschi.model.project import Project, short_id
from brunelleschi.model.units import LENGTH_TOLERANCE, MAX_ABS_COORDINATE, lengths_equal
from brunelleschi.model.wall import Point, TopAtLevel, UnconnectedHeight, Wall, WallTop

__all__ = [
    "LENGTH_TOLERANCE",
    "MAX_ABS_COORDINATE",
    "Level",
    "Point",
    "Project",
    "TopAtLevel",
    "UnconnectedHeight",
    "Wall",
    "WallTop",
    "lengths_equal",
    "short_id",
]
