"""The public scripting API.

Scripts, the ``bbim`` command and the future interface all use this module. Names here
are kept stable; internals may move.

>>> from brunelleschi import api
>>> project = api.new_project("House")
>>> ground = api.add_level(project, "Ground floor", 0.0)
>>> first = api.add_level(project, "First floor", 3.0)
>>> wall = api.add_wall(project, (0, 0), (5, 0), 0.3, ground.id, top_level=first.id)
>>> api.set_level_elevation(project, first.id, 3.2)  # the wall follows
>>> api.save(project, "house.bbim")
"""

from __future__ import annotations

from brunelleschi.commands import (
    add_level,
    add_wall,
    delete_level,
    delete_wall,
    modify_wall,
    rename_level,
    set_level_elevation,
    transaction,
)
from brunelleschi.errors import (
    AmbiguousReferenceError,
    BrunelleschiError,
    ModelError,
    NotFoundError,
    ProjectFileError,
    UnsupportedSchemaVersionError,
)
from brunelleschi.geometry import Join, JoinIssue, JoinKind
from brunelleschi.model import (
    Level,
    Point,
    Project,
    TopAtLevel,
    UnconnectedHeight,
    Wall,
    short_id,
)
from brunelleschi.regen import WallFootprint, WallGeometry, wall_geometry
from brunelleschi.storage import CURRENT_SCHEMA_VERSION, dumps, json_schema, load, loads, save


def new_project(name: str) -> Project:
    """An empty project."""
    project = Project(name=name.strip())
    project.check()
    return project


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "AmbiguousReferenceError",
    "BrunelleschiError",
    "Join",
    "JoinIssue",
    "JoinKind",
    "Level",
    "ModelError",
    "NotFoundError",
    "Point",
    "Project",
    "ProjectFileError",
    "TopAtLevel",
    "UnconnectedHeight",
    "UnsupportedSchemaVersionError",
    "Wall",
    "WallFootprint",
    "WallGeometry",
    "add_level",
    "add_wall",
    "delete_level",
    "delete_wall",
    "dumps",
    "json_schema",
    "load",
    "loads",
    "modify_wall",
    "new_project",
    "rename_level",
    "save",
    "set_level_elevation",
    "short_id",
    "transaction",
    "wall_geometry",
]
