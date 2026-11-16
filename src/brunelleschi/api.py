"""The public scripting API.

Scripts, the ``bbim`` command and the future interface all use this module. Names here
are kept stable; internals may move.

>>> from brunelleschi import api
>>> project = api.new_project("House")
>>> api.add_level(project, "Ground floor", 0.0)
>>> api.add_level(project, "First floor", 3.0)
>>> api.save(project, "house.bbim")
"""

from __future__ import annotations

from brunelleschi.commands import (
    add_level,
    delete_level,
    rename_level,
    set_level_elevation,
    transaction,
)
from brunelleschi.errors import (
    BrunelleschiError,
    ModelError,
    NotFoundError,
    ProjectFileError,
    UnsupportedSchemaVersionError,
)
from brunelleschi.model import Level, Project
from brunelleschi.storage import dumps, json_schema, load, loads, save


def new_project(name: str) -> Project:
    """An empty project."""
    project = Project(name=name.strip())
    project.check()
    return project


__all__ = [
    "BrunelleschiError",
    "Level",
    "ModelError",
    "NotFoundError",
    "Project",
    "ProjectFileError",
    "UnsupportedSchemaVersionError",
    "add_level",
    "delete_level",
    "dumps",
    "json_schema",
    "load",
    "loads",
    "new_project",
    "rename_level",
    "save",
    "set_level_elevation",
    "transaction",
]
