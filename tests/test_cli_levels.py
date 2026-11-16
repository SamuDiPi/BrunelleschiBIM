"""The ``bbim`` project and level commands, end to end through files."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from brunelleschi import api
from brunelleschi.cli import main


@pytest.fixture
def house(tmp_path: Path) -> Path:
    path = tmp_path / "house.bbim"
    assert main(["new", str(path), "--name", "House"]) == 0
    return path


def _levels(path: Path, capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    capsys.readouterr()
    assert main(["level", "list", str(path), "--json"]) == 0
    rows: list[dict[str, object]] = json.loads(capsys.readouterr().out)
    return rows


def test_new_creates_an_empty_project(house: Path) -> None:
    project = api.load(house)
    assert project.name == "House"
    assert project.levels == []


def test_new_takes_the_name_from_the_file(tmp_path: Path) -> None:
    path = tmp_path / "Villa Rossi.bbim"
    assert main(["new", str(path)]) == 0
    assert api.load(path).name == "Villa Rossi"


def test_new_does_not_overwrite(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["level", "add", str(house), "Ground floor", "0"])
    assert main(["new", str(house)]) == 1
    assert "already exists" in capsys.readouterr().err
    assert len(api.load(house).levels) == 1
    assert main(["new", str(house), "--force"]) == 0
    assert api.load(house).levels == []


def test_full_level_workflow(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = str(house)
    assert main(["level", "add", f, "Ground floor", "0"]) == 0
    assert main(["level", "add", f, "First floor", "3,00"]) == 0  # decimal comma
    assert main(["level", "add", f, "Basement", "-2.80"]) == 0
    assert "added level 'Basement' at -2.800 m" in capsys.readouterr().out

    rows = _levels(house, capsys)
    assert [(r["name"], r["elevation"]) for r in rows] == [
        ("Basement", -2.8),
        ("Ground floor", 0.0),
        ("First floor", 3.0),
    ]

    assert main(["level", "move", f, "first floor", "3.20"]) == 0
    assert "from +3.000 m to +3.200 m" in capsys.readouterr().out
    assert main(["level", "rename", f, "First floor", "Level 1"]) == 0
    assert main(["level", "delete", f, "Basement"]) == 0
    rows = _levels(house, capsys)
    assert [(r["name"], r["elevation"]) for r in rows] == [("Ground floor", 0.0), ("Level 1", 3.2)]


def test_list_shows_highest_first(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["level", "add", str(house), "Ground floor", "0"])
    main(["level", "add", str(house), "Roof", "6"])
    capsys.readouterr()
    assert main(["level", "list", str(house)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split("  ")[-1] for line in lines] == ["Roof", "Ground floor"]


def test_list_of_empty_project(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()
    assert main(["level", "list", str(house)]) == 0
    assert capsys.readouterr().out.strip() == "no levels"


def test_info(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["level", "add", str(house), "Ground floor", "0"])
    capsys.readouterr()
    assert main(["info", str(house)]) == 0
    out = capsys.readouterr().out
    assert "project: House" in out
    assert "levels:  1" in out


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["level", "add", "{f}", "Ground floor", "1"], "unique"),
        (["level", "rename", "{f}", "Attic", "X"], "no level named 'Attic'"),
        (["level", "move", "{f}", "Attic", "1"], "no level named 'Attic'"),
        (["level", "delete", "{f}", "Attic"], "no level named 'Attic'"),
        (["level", "move", "{f}", "Ground floor", "1e9"], "elevation"),
        (["info", "{missing}"], "file not found"),
    ],
)
def test_errors_exit_with_1_and_leave_the_file_unchanged(
    house: Path, capsys: pytest.CaptureFixture[str], argv: list[str], message: str
) -> None:
    main(["level", "add", str(house), "Ground floor", "0"])
    before = house.read_bytes()
    capsys.readouterr()
    args = [a.format(f=house, missing=house.with_name("missing.bbim")) for a in argv]
    assert main(args) == 1
    err = capsys.readouterr().err
    assert err.startswith("bbim: error: ")
    assert message in err
    assert house.read_bytes() == before


def test_bad_number_is_a_usage_error(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["level", "add", str(house), "Roof", "three"])
    assert exit_info.value.code == 2
    assert "not a number of metres" in capsys.readouterr().err


def test_schema_command_prints_the_schema(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schema"]) == 0
    assert json.loads(capsys.readouterr().out) == api.json_schema()


def test_real_process_round_trip(tmp_path: Path) -> None:
    """The same workflow as a user types it, in separate processes."""
    path = tmp_path / "casa.bbim"

    def bbim(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "brunelleschi.cli", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    assert bbim("new", str(path), "--name", "Casa").returncode == 0
    assert bbim("level", "add", str(path), "Piano terra", "0").returncode == 0
    assert bbim("level", "add", str(path), "Primo piano", "3,15").returncode == 0
    result = bbim("level", "add", str(path), "piano TERRA", "9")
    assert result.returncode == 1
    assert "unique" in result.stderr
    listing = bbim("level", "list", str(path), "--json")
    assert [r["name"] for r in json.loads(listing.stdout)] == ["Piano terra", "Primo piano"]
