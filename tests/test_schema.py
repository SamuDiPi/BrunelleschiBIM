"""The published JSON Schema of the .bbim file."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from brunelleschi import api

SCHEMA_FILE = Path(__file__).parent.parent / "schemas" / "bbim-1.schema.json"


def _published() -> dict[str, object]:
    data: dict[str, object] = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    return data


def test_published_schema_is_up_to_date() -> None:
    assert _published() == api.json_schema(), (
        "schemas/bbim-1.schema.json is out of date; regenerate it with `bbim schema`"
    )


def test_published_schema_is_a_valid_schema() -> None:
    jsonschema.Draft202012Validator.check_schema(_published())


def test_saved_files_validate_against_the_schema() -> None:
    project = api.new_project("House")
    api.add_level(project, "Ground floor", 0.0)
    api.add_level(project, "First floor", 3.0)
    jsonschema.validate(json.loads(api.dumps(project)), _published())


@pytest.mark.parametrize(
    "bad",
    [
        {"format": "brunelleschi-project", "schema_version": 2, "name": "P", "levels": []},
        {"format": "brunelleschi-project", "schema_version": 1, "name": "", "levels": []},
        {"format": "brunelleschi-project", "schema_version": 1, "name": "P", "levels": [{}]},
        {"format": "x", "schema_version": 1, "name": "P", "levels": []},
    ],
)
def test_schema_rejects_bad_files(bad: dict[str, object]) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, _published())
