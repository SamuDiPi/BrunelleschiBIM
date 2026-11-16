"""The .bbim file: round trip, determinism, versions and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from brunelleschi import api
from brunelleschi.errors import ProjectFileError, UnsupportedSchemaVersionError
from brunelleschi.storage import migrations


@pytest.fixture
def project() -> api.Project:
    p = api.new_project("Casa è bella")
    api.add_level(p, "Piano terra", 0.0)
    api.add_level(p, "Primo piano", 3.15)
    api.add_level(p, "Interrato", -2.8)
    return p


def _raw(project: api.Project) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(api.dumps(project))
    return data


def test_round_trip_gives_an_equal_model(project: api.Project, tmp_path: Path) -> None:
    path = tmp_path / "house.bbim"
    api.save(project, path)
    loaded = api.load(path)
    assert loaded == project
    assert [lv.id for lv in loaded.levels] == [lv.id for lv in project.levels]


def test_saving_twice_gives_identical_bytes(project: api.Project, tmp_path: Path) -> None:
    a, b = tmp_path / "a.bbim", tmp_path / "b.bbim"
    api.save(project, a)
    api.save(api.load(a), b)
    assert a.read_bytes() == b.read_bytes()


def test_file_is_utf8_with_lf_and_sorted_keys(project: api.Project, tmp_path: Path) -> None:
    path = tmp_path / "house.bbim"
    api.save(project, path)
    data = path.read_bytes()
    assert b"\r\n" not in data
    assert data.endswith(b"}\n")
    assert "Casa è bella".encode() in data
    keys = list(json.loads(data))
    assert keys == sorted(keys)


def test_file_header(project: api.Project) -> None:
    raw = _raw(project)
    assert raw["format"] == "brunelleschi-project"
    assert raw["schema_version"] == 1


def test_negative_zero_is_written_as_zero() -> None:
    p = api.new_project("P")
    api.add_level(p, "L", -0.0)
    assert '"elevation": 0.0' in api.dumps(p)
    assert "-0.0" not in api.dumps(p)


def test_save_does_not_leave_temporary_files(project: api.Project, tmp_path: Path) -> None:
    api.save(project, tmp_path / "house.bbim")
    api.save(project, tmp_path / "house.bbim")
    assert [p.name for p in tmp_path.iterdir()] == ["house.bbim"]


def test_newer_schema_version_is_refused(project: api.Project) -> None:
    raw = _raw(project)
    raw["schema_version"] = 2
    with pytest.raises(UnsupportedSchemaVersionError, match="reads up to version 1"):
        api.loads(json.dumps(raw))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("not json", "not a valid JSON document"),
        ("[]", "not a BrunelleschiBIM project file"),
        ('{"format": "something-else"}', "not a BrunelleschiBIM project file"),
        ('{"format": "brunelleschi-project"}', "invalid schema_version"),
        ('{"format": "brunelleschi-project", "schema_version": "1"}', "invalid schema_version"),
        ('{"format": "brunelleschi-project", "schema_version": true}', "invalid schema_version"),
        ('{"format": "brunelleschi-project", "schema_version": 0}', "invalid schema_version"),
    ],
)
def test_not_a_project_file(text: str, message: str) -> None:
    with pytest.raises(ProjectFileError, match=message):
        api.loads(text)


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda r: r.pop("levels"),
        lambda r: r.update(extra_field=1),
        lambda r: r["levels"][0].update(elevation="three"),
        lambda r: r["levels"][0].update(elevation=1e9),
        lambda r: r["levels"][0].update(id="not-a-uuid"),
        lambda r: r["levels"][0].update(name=""),
        lambda r: r["levels"][1].update(name=r["levels"][0]["name"].upper()),
        lambda r: r["levels"][1].update(id=r["levels"][0]["id"]),
    ],
)
def test_invalid_content_is_refused(project: api.Project, corrupt: Any) -> None:
    raw = _raw(project)
    corrupt(raw)
    with pytest.raises(ProjectFileError, match="invalid project file"):
        api.loads(json.dumps(raw))


def test_nan_in_file_is_refused(project: api.Project) -> None:
    text = api.dumps(project).replace('"elevation": 0.0', '"elevation": NaN', 1)
    with pytest.raises(ProjectFileError):
        api.loads(text)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ProjectFileError, match="file not found"):
        api.load(tmp_path / "nope.bbim")


def test_binary_file(tmp_path: Path) -> None:
    path = tmp_path / "x.bbim"
    path.write_bytes(b"\xff\xfe\x00garbage")
    with pytest.raises(ProjectFileError, match="UTF-8"):
        api.load(path)


def test_migrations_run_step_by_step(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def step(n: int) -> migrations.Migration:
        def run(data: migrations.RawFile) -> migrations.RawFile:
            calls.append(data["schema_version"])
            data[f"step{n}"] = True
            return data

        return run

    monkeypatch.setattr(migrations, "MIGRATIONS", {1: step(1), 2: step(2)})
    result = migrations.upgrade({"schema_version": 1}, 1, 3)
    assert calls == [1, 2]
    assert result == {"schema_version": 3, "step1": True, "step2": True}


def test_missing_migration_is_reported() -> None:
    with pytest.raises(UnsupportedSchemaVersionError, match="cannot be upgraded"):
        migrations.upgrade({"schema_version": 1}, 1, 2)
