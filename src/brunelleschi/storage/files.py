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
from brunelleschi.model import Level, Project
from brunelleschi.storage.migrations import upgrade
from brunelleschi.storage.schema_v1 import FORMAT_NAME, LevelV1, ProjectFileV1

FILE_FORMAT = FORMAT_NAME
CURRENT_SCHEMA_VERSION = 1


def _number(value: float) -> float:
    # -0.0 and 0.0 are the same elevation; write them the same way.
    return 0.0 if value == 0 else value


def to_file_model(project: Project) -> ProjectFileV1:
    return ProjectFileV1(
        format="brunelleschi-project",
        schema_version=1,
        name=project.name,
        levels=[
            LevelV1(id=lv.id, name=lv.name, elevation=_number(lv.elevation))
            for lv in project.levels
        ],
    )


def from_file_model(data: ProjectFileV1) -> Project:
    project = Project(name=data.name)
    for lv in data.levels:
        project._add_level(Level(id=lv.id, name=lv.name, elevation=lv.elevation))
    return project


def dumps(project: Project) -> str:
    """The project as the text of a ``.bbim`` file."""
    project.check()
    payload = to_file_model(project).model_dump(mode="json")
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
        data = ProjectFileV1.model_validate(raw)
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


def json_schema() -> dict[str, Any]:
    """The JSON Schema of the current file version."""
    return ProjectFileV1.model_json_schema()
