"""Exceptions raised by the core. Every error a user can cause is a ``BrunelleschiError``."""

from __future__ import annotations


class BrunelleschiError(Exception):
    """Base class for errors caused by invalid input or invalid model state."""


class ModelError(BrunelleschiError):
    """A change would leave the model in an invalid state. The change was not applied."""


class NotFoundError(BrunelleschiError):
    """An element looked up by id or name does not exist."""


class AmbiguousReferenceError(BrunelleschiError):
    """A short id matches more than one element; a longer prefix is needed."""


class DrawingError(BrunelleschiError):
    """A drawing cannot be produced as asked (it does not fit the sheet, bad options)."""


class ProjectFileError(BrunelleschiError):
    """A project file cannot be read: wrong format, corrupt content or invalid data."""


class UnsupportedSchemaVersionError(ProjectFileError):
    """A project file uses a schema version this software cannot read."""
