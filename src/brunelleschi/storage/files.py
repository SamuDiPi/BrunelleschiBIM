"""Reading and writing ``.bbim`` files.

Writing is deterministic: the same model always produces the same bytes (stable element
order, sorted keys, shortest round-trip float repr, LF line endings, UTF-8). That keeps
``git diff`` meaningful and makes saving idempotent.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from brunelleschi.errors import ModelError, ProjectFileError, UnsupportedSchemaVersionError
from brunelleschi.model import Level, Point, Project, TopAtLevel, UnconnectedHeight, Wall
from brunelleschi.storage.migrations import upgrade
from brunelleschi.storage.schema_v1 import FORMAT_NAME, LevelV1, ProjectFileV1
from brunelleschi.storage.schema_v2 import (
    ProjectFileV2,
    WallBaseV2,
    WallTopAtLevelV2,
    WallTopHeightV2,
    WallV2,
)

FILE_FORMAT = FORMAT_NAME
CURRENT_SCHEMA_VERSION = 2
CurrentFile = ProjectFileV2

# Every released file version, for publishing its schema. Never remove an entry.
_FILE_MODELS: dict[int, type[ProjectFileV1] | type[ProjectFileV2]] = {
    1: ProjectFileV1,
    2: ProjectFileV2,
}


def _wall_to_file(wall: Wall) -> WallV2:
    top: WallTopAtLevelV2 | WallTopHeightV2
    if isinstance(wall.top, TopAtLevel):
        top = WallTopAtLevelV2(kind="level", level=wall.top.level_id, offset=wall.top.offset)
    else:
        top = WallTopHeightV2(kind="height", height=wall.top.height)
    return WallV2(
        id=wall.id,
        start=(wall.start.x, wall.start.y),
        end=(wall.end.x, wall.end.y),
        thickness=wall.thickness,
        base=WallBaseV2(level=wall.base_level_id, offset=wall.base_offset),
        top=top,
    )


def _wall_from_file(data: WallV2) -> Wall:
    top: TopAtLevel | UnconnectedHeight
    if isinstance(data.top, WallTopAtLevelV2):
        top = TopAtLevel(data.top.level, data.top.offset)
    else:
        top = UnconnectedHeight(data.top.height)
    return Wall(
        id=data.id,
        start=Point(*data.start),
        end=Point(*data.end),
        thickness=data.thickness,
        base_level_id=data.base.level,
        base_offset=data.base.offset,
        top=top,
    )


def to_file_model(project: Project) -> CurrentFile:
    return ProjectFileV2(
        format="brunelleschi-project",
        schema_version=2,
        name=project.name,
        levels=[LevelV1(id=lv.id, name=lv.name, elevation=lv.elevation) for lv in project.levels],
        walls=[_wall_to_file(w) for w in project.walls],
    )


def from_file_model(data: CurrentFile) -> Project:
    project = Project(name=data.name)
    for lv in data.levels:
        project._add_level(Level(id=lv.id, name=lv.name, elevation=lv.elevation))
    for wall in data.walls:
        project._add_wall(_wall_from_file(wall))
    return project


def _normalize(value: Any) -> Any:
    """-0.0 and 0.0 are the same length; write them the same way."""
    if isinstance(value, float):
        return 0.0 if value == 0 else value
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def dumps(project: Project) -> str:
    """The project as the text of a ``.bbim`` file."""
    project.check()
    payload = _normalize(to_file_model(project).model_dump(mode="json"))
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def loads(text: str) -> Project:
    """A project from the text of a ``.bbim`` file, upgrading older versions."""
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProjectFileError(f"not a valid JSON document: {exc}") from None
    if not isinstance(raw, dict) or raw.get("format") != FORMAT_NAME:
        raise ProjectFileError("not a BrunelleschiBIM project file")
    version = raw.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ProjectFileError(f"invalid schema_version: {version!r}")
    if version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(
            f"the file uses schema version {version}, but this version of BrunelleschiBIM "
            f"reads up to version {CURRENT_SCHEMA_VERSION}. Update BrunelleschiBIM to open it."
        )
    raw = upgrade(raw, version, CURRENT_SCHEMA_VERSION)
    try:
        data = CurrentFile.model_validate(raw)
    except ValidationError as exc:
        raise ProjectFileError(f"invalid project file:\n{exc}") from None
    try:
        project = from_file_model(data)
        project.check()
    except ModelError as exc:
        raise ProjectFileError(f"invalid project file: {exc}") from None
    return project


def save(project: Project, path: str | os.PathLike[str]) -> None:
    """Write a project file. The old file is replaced only once the new one is complete."""
    target = Path(path)
    text = dumps(project)
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        Path(tmp).replace(target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load(path: str | os.PathLike[str]) -> Project:
    """Read a project file."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ProjectFileError(f"file not found: {path}") from None
    except UnicodeDecodeError:
        raise ProjectFileError(f"not a text file (UTF-8 expected): {path}") from None
    return loads(text)


def json_schema(version: int = CURRENT_SCHEMA_VERSION) -> dict[str, Any]:
    """The JSON Schema of a file version (the current one by default)."""
    try:
        return _FILE_MODELS[version].model_json_schema()
    except KeyError:
        raise UnsupportedSchemaVersionError(f"no schema version {version}") from None
