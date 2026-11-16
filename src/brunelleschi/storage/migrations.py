"""Upgrades of project files written by older versions.

``MIGRATIONS[n]`` turns the raw JSON of schema version ``n`` into version ``n + 1``.
Each migration is a small pure function with its own test and sample file
(``tests/data/v<n>-sample.bbim``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from brunelleschi.errors import ProjectFileError, UnsupportedSchemaVersionError

RawFile = dict[str, Any]
Migration = Callable[[RawFile], RawFile]


def _v1_to_v2(data: RawFile) -> RawFile:
    """Version 2 adds walls; a version 1 file has none."""
    if "walls" in data:  # not valid version 1; do not silently drop what it holds
        raise ProjectFileError("invalid project file: version 1 files cannot contain walls")
    data["walls"] = []
    return data


MIGRATIONS: dict[int, Migration] = {1: _v1_to_v2}


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
