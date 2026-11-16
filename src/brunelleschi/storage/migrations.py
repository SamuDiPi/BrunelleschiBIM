"""Upgrades of project files written by older versions.

``MIGRATIONS[n]`` turns the raw JSON of schema version ``n`` into version ``n + 1``.
Each migration is a small pure function with its own test and sample file
(``tests/data/v<n>-sample.bbim``).
"""

from __future__ import annotations

import json
import uuid
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


def _v2_to_v3(data: RawFile) -> RawFile:
    """Version 3 adds doors and windows; a version 2 file has none."""
    for key in ("doors", "windows"):
        if key in data:
            raise ProjectFileError(f"invalid project file: version 2 files cannot contain {key}")
        data[key] = []
    return data


# Namespace for ids that migrations derive from file content.
_MIGRATION_NAMESPACE = uuid.UUID("5f0c8a52-3c1e-4c55-9d1b-b4f1a8e2d7c3")


def _v3_to_v4(data: RawFile) -> RawFile:
    """Version 4 gives the project a stable id.

    The id is derived from the file's content, so opening the same version 3 file twice
    gives the same id (and the same IFC identifiers) even before it is saved again.
    """
    if "id" in data:
        raise ProjectFileError("invalid project file: version 3 files cannot contain an id")
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    data["id"] = str(uuid.uuid5(_MIGRATION_NAMESPACE, canonical))
    return data


def _v4_to_v5(data: RawFile) -> RawFile:
    """Version 5 adds links to IFC files; a version 4 file has none."""
    if "references" in data:
        raise ProjectFileError("invalid project file: version 4 files cannot contain references")
    data["references"] = []
    return data


MIGRATIONS: dict[int, Migration] = {1: _v1_to_v2, 2: _v2_to_v3, 3: _v3_to_v4, 4: _v4_to_v5}


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
