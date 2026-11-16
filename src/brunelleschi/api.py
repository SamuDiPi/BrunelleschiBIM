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
    add_door,
    add_level,
    add_wall,
    add_window,
    delete_hosted,
    delete_level,
    delete_wall,
    modify_hosted,
    modify_wall,
    rename_level,
    set_level_elevation,
    transaction,
)
from brunelleschi.drawings import Sheet, plan_svg, plan_view, write_plan_svg
from brunelleschi.errors import (
    AmbiguousReferenceError,
    BrunelleschiError,
    DrawingError,
    ModelError,
    NotFoundError,
    ProjectFileError,
    UnsupportedSchemaVersionError,
)
from brunelleschi.geometry import Join, JoinIssue, JoinKind
from brunelleschi.model import (
    Door,
    HostedElement,
    Jamb,
    Level,
    Point,
    Project,
    Side,
    TopAtLevel,
    UnconnectedHeight,
    Wall,
    Window,
    short_id,
)
from brunelleschi.regen import OpeningGeometry, WallFootprint, WallGeometry, wall_geometry
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
    "Door",
    "DrawingError",
    "HostedElement",
    "Jamb",
    "Join",
    "JoinIssue",
    "JoinKind",
    "Level",
    "ModelError",
    "NotFoundError",
    "OpeningGeometry",
    "Point",
    "Project",
    "ProjectFileError",
    "Sheet",
    "Side",
    "TopAtLevel",
    "UnconnectedHeight",
    "UnsupportedSchemaVersionError",
    "Wall",
    "WallFootprint",
    "WallGeometry",
    "Window",
    "add_door",
    "add_level",
    "add_wall",
    "add_window",
    "delete_hosted",
    "delete_level",
    "delete_wall",
    "dumps",
    "json_schema",
    "load",
    "loads",
    "modify_hosted",
    "modify_wall",
    "new_project",
    "plan_svg",
    "plan_view",
    "rename_level",
    "save",
    "set_level_elevation",
    "short_id",
    "transaction",
    "wall_geometry",
    "write_plan_svg",
]
