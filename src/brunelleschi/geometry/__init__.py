"""Plan geometry derived from the model: wall footprints and wall joins.

This package works on plain data (``WallLine``), not on model objects, so it can be tested
alone and reused by drawings and exporters. It never changes the model.
"""

from brunelleschi.geometry.joins import (
    EndCorners,
    Join,
    JoinIssue,
    JoinKind,
    WallLine,
    crossings,
    footprint,
    point_key,
    solve_point,
)

__all__ = [
    "EndCorners",
    "Join",
    "JoinIssue",
    "JoinKind",
    "WallLine",
    "crossings",
    "footprint",
    "point_key",
    "solve_point",
]
