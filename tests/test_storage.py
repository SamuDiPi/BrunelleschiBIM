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
    assert raw["schema_version"] == 2


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
    raw["schema_version"] = 3
    with pytest.raises(UnsupportedSchemaVersionError, match="reads up to version 2"):
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
        migrations.upgrade({"schema_version": 2}, 2, 3)


# ------------------------------------------------------------------ version 1 -> 2

V1_SAMPLE = Path(__file__).parent / "data" / "v1-sample.bbim"


def test_v1_sample_is_upgraded() -> None:
    """A file really written by the version 1 code (M1) opens, with no walls."""
    project = api.load(V1_SAMPLE)
    assert project.name == "Casa Rossi"
    assert [lv.name for lv in project.levels_by_elevation()][:2] == ["Fondazioni", "Interrato"]
    assert project.walls == []
    assert json.loads(api.dumps(project))["schema_version"] == 2


def test_v1_file_with_walls_is_refused() -> None:
    raw = json.loads(V1_SAMPLE.read_text(encoding="utf-8"))
    raw["walls"] = [{"anything": 1}]
    with pytest.raises(ProjectFileError, match="version 1 files cannot contain walls"):
        api.loads(json.dumps(raw))


# ------------------------------------------------------------------------ walls


@pytest.fixture
def with_walls(project: api.Project) -> api.Project:
    ground, first = project.level("Piano terra"), project.level("Primo piano")
    api.add_wall(project, (0, 0), (6.5, 0), 0.3, ground.id, top_level=first.id, top_offset=-0.2)
    api.add_wall(project, (6.5, 0), (6.5, 4.25), 0.25, ground.id, base_offset=-0.0, height=2.7)
    return project


def test_walls_round_trip(with_walls: api.Project, tmp_path: Path) -> None:
    path = tmp_path / "house.bbim"
    api.save(with_walls, path)
    loaded = api.load(path)
    assert loaded == with_walls
    api.save(loaded, tmp_path / "again.bbim")
    assert (tmp_path / "again.bbim").read_bytes() == path.read_bytes()


def test_wall_file_layout(with_walls: api.Project) -> None:
    walls = _raw(with_walls)["walls"]
    first, second = walls
    assert first["start"] == [0.0, 0.0]
    assert first["end"] == [6.5, 0.0]
    assert first["top"] == {
        "kind": "level",
        "level": str(with_walls.level("Primo piano").id),
        "offset": -0.2,
    }
    assert second["top"] == {"kind": "height", "height": 2.7}
    assert second["base"]["offset"] == 0.0
    assert "-0.0" not in api.dumps(with_walls)
    # Derived values are never stored.
    for key in ("length", "base_z", "top_z", "height_z"):
        assert key not in first


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda r: r["walls"][0].update(thickness=0),
        lambda r: r["walls"][0].update(start=[0, 0, 0]),
        lambda r: r["walls"][0].update(end=r["walls"][0]["start"]),
        lambda r: r["walls"][0]["top"].update(kind="roof"),
        lambda r: r["walls"][1]["top"].update(height=-1),
        lambda r: r["walls"][0]["base"].update(level="6f1c0e8e-0000-4000-8000-000000000000"),
        lambda r: r["walls"][1].update(id=r["walls"][0]["id"]),
        lambda r: r["walls"][0]["top"].update(offset=-10),  # top below base
    ],
)
def test_invalid_walls_are_refused(with_walls: api.Project, corrupt: Any) -> None:
    raw = _raw(with_walls)
    corrupt(raw)
    with pytest.raises(ProjectFileError, match="invalid project file"):
        api.loads(json.dumps(raw))
