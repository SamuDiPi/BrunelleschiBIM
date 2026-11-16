"""Upgrades of project files written by older versions.

``MIGRATIONS[n]`` turns the raw JSON of schema version ``n`` into version ``n + 1``.
Each migration is a small pure function with its own test and sample file. Version 1 is
the first version, so there are no migrations yet.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from brunelleschi.errors import UnsupportedSchemaVersionError

RawFile = dict[str, Any]
Migration = Callable[[RawFile], RawFile]

MIGRATIONS: dict[int, Migration] = {}


def upgrade(data: RawFile, from_version: int, to_version: int) -> RawFile:
    """Apply migrations one step at a time until ``to_version``."""
    version = from_version
    while version < to_version:
        step = MIGRATIONS.get(version)
        if step is None:
            raise UnsupportedSchemaVersionError(
                f"files with schema version {version} cannot be upgraded by this version "
                "of BrunelleschiBIM"
            )
        data = step(dict(data))
        version += 1
        data["schema_version"] = version
    return data
