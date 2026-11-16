"""The published JSON Schemas of the .bbim file."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from brunelleschi import api

SCHEMAS = Path(__file__).parent.parent / "schemas"
VERSIONS = range(1, api.CURRENT_SCHEMA_VERSION + 1)


def _published(version: int) -> dict[str, object]:
    path = SCHEMAS / f"bbim-{version}.schema.json"
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("version", VERSIONS)
def test_published_schema_is_up_to_date(version: int) -> None:
    """Released schemas never change; the current one matches the code."""
    assert _published(version) == api.json_schema(version), (
        f"schemas/bbim-{version}.schema.json differs from the code. For the current version, "
        f"regenerate it with `bbim schema -o`; a released version must never change."
    )


@pytest.mark.parametrize("version", VERSIONS)
def test_published_schema_is_a_valid_schema(version: int) -> None:
    jsonschema.Draft202012Validator.check_schema(_published(version))


def test_schema_files_are_lf_only() -> None:
    for path in SCHEMAS.glob("*.json"):
        assert b"\r\n" not in path.read_bytes(), path.name


def test_saved_files_validate_against_the_current_schema() -> None:
    project = api.new_project("House")
    ground = api.add_level(project, "Ground floor", 0.0)
    first = api.add_level(project, "First floor", 3.0)
    api.add_wall(project, (0, 0), (5, 0), 0.3, ground.id, top_level=first.id)
    w = api.add_wall(project, (5, 0), (5, 4), 0.3, ground.id, height=2.5)
    api.add_door(project, w.id, 1.0, 0.9, 2.1)
    api.add_window(project, w.id, 3.0, 1.0, 1.0, 1.0)
    jsonschema.validate(json.loads(api.dumps(project)), _published(api.CURRENT_SCHEMA_VERSION))


@pytest.mark.parametrize("version", [1, 2])
def test_samples_validate_against_their_schema(version: int) -> None:
    path = Path(__file__).parent / "data" / f"v{version}-sample.bbim"
    jsonschema.validate(json.loads(path.read_text("utf-8")), _published(version))


def _file(**changes: object) -> dict[str, object]:
    base: dict[str, object] = {
        "format": "brunelleschi-project",
        "schema_version": 2,
        "name": "P",
        "levels": [],
        "walls": [],
    }
    base.update(changes)
    return base


_WALL = {
    "id": "6f1c0e8e-0000-4000-8000-000000000001",
    "start": [0, 0],
    "end": [5, 0],
    "thickness": 0.3,
    "base": {"level": "6f1c0e8e-0000-4000-8000-000000000002", "offset": 0},
    "top": {"kind": "height", "height": 3},
}


@pytest.mark.parametrize(
    "bad",
    [
        _file(schema_version=3),
        _file(name=""),
        _file(levels=[{}]),
        _file(format="x"),
        _file(walls=[{**_WALL, "thickness": 0}]),
        _file(walls=[{**_WALL, "start": [0, 0, 0]}]),
        _file(walls=[{**_WALL, "top": {"kind": "height", "height": 3, "level": "x"}}]),
        _file(walls=[{**_WALL, "top": {"kind": "level", "offset": 0}}]),
        _file(walls=[{**_WALL, "length": 5}]),
    ],
)
def test_schema_rejects_bad_files(bad: dict[str, object]) -> None:
    jsonschema.validate(_file(walls=[_WALL]), _published(2))  # the base case is valid
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, _published(2))


def test_v3_schema_rejects_a_bad_door() -> None:
    door = {
        "id": "6f1c0e8e-0000-4000-8000-000000000003",
        "host": _WALL["id"],
        "position": 1,
        "width": 0.9,
        "height": 2.1,
        "sill_height": 0,
        "swing": {"side": "left", "hinge": "start"},
    }
    good = {**_file(walls=[_WALL]), "schema_version": 3, "doors": [door], "windows": []}
    jsonschema.validate(good, _published(3))
    for bad_door in (
        {**door, "swing": {"side": "up", "hinge": "start"}},
        {**door, "width": 0},
        {k: v for k, v in door.items() if k != "swing"},
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({**good, "doors": [bad_door]}, _published(3))
