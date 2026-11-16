"""The ``bbim wall`` commands, end to end through files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brunelleschi import api
from brunelleschi.cli import main


@pytest.fixture
def house(tmp_path: Path) -> Path:
    path = tmp_path / "house.bbim"
    assert main(["new", str(path)]) == 0
    assert main(["level", "add", str(path), "Piano terra", "0"]) == 0
    assert main(["level", "add", str(path), "Primo piano", "3,00"]) == 0
    return path


def _add(house: Path, *extra: str) -> int:
    return main(
        [
            "wall", "add", str(house),
            "--start", "0", "0", "--end", "6,5", "0",
            "--thickness", "0,30", "--base", "Piano terra",
            *extra,
        ]
    )  # fmt: skip


def _walls(house: Path, capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    capsys.readouterr()
    assert main(["wall", "list", str(house), "--json"]) == 0
    rows: list[dict[str, object]] = json.loads(capsys.readouterr().out)
    return rows


def test_add_wall_to_top_level(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _add(house, "--top", "primo piano", "--top-offset", "-0,20") == 0
    out = capsys.readouterr().out
    assert "added wall" in out
    assert "L 6.500 m" in out
    assert "z +0.000 .. +2.800 m" in out
    (row,) = _walls(house, capsys)
    assert row["start"] == [0.0, 0.0]
    assert row["end"] == [6.5, 0.0]
    assert row["thickness"] == 0.3
    assert row["base_level"] == "Piano terra"
    assert row["top_level"] == "Primo piano"
    assert row["top_offset"] == -0.2
    assert (row["base_z"], row["top_z"]) == (0.0, 2.8)


def test_add_wall_with_height_and_negative_coordinates(
    house: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["wall", "add", str(house), "--start", "-2", "-1.5", "--end", "-2", "3"]
    args += ["--thickness", "0.2", "--base", "Primo piano", "--height", "1,10"]
    assert main(args) == 0
    (row,) = _walls(house, capsys)
    assert row["start"] == [-2.0, -1.5]
    assert row["height"] == 1.1
    assert "top_level" not in row
    assert (row["base_z"], row["top_z"]) == (3.0, 4.1)


def test_level_move_reports_and_moves_walls(
    house: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _add(house, "--top", "Primo piano")
    wall_id = _walls(house, capsys)[0]["id"]
    assert main(["level", "move", str(house), "Primo piano", "3.20"]) == 0
    out = capsys.readouterr().out
    assert f"1 wall(s) follow: {str(wall_id)[:8]}" in out
    (row,) = _walls(house, capsys)
    assert row["top_z"] == 3.2


def test_level_move_that_inverts_a_wall_fails(
    house: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _add(house, "--top", "Primo piano")
    before = house.read_bytes()
    capsys.readouterr()
    assert main(["level", "move", str(house), "Primo piano", "-1"]) == 1
    assert "must be above base" in capsys.readouterr().err
    assert house.read_bytes() == before


def test_level_delete_lists_walls(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _add(house, "--top", "Primo piano")
    wall_id = str(_walls(house, capsys)[0]["id"])
    assert main(["level", "delete", str(house), "Primo piano"]) == 1
    err = capsys.readouterr().err
    assert "cannot be deleted" in err
    assert wall_id[:8] in err


def test_modify_and_delete(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _add(house, "--top", "Primo piano")
    short = str(_walls(house, capsys)[0]["id"])[:6]
    assert main(["wall", "modify", str(house), short, "--end", "4", "0", "--height", "2.5"]) == 0
    (row,) = _walls(house, capsys)
    assert row["end"] == [4.0, 0.0]
    assert row["height"] == 2.5
    assert main(["wall", "modify", str(house), short, "--top", "Primo piano"]) == 0
    assert _walls(house, capsys)[0]["top_level"] == "Primo piano"
    assert main(["wall", "delete", str(house), short]) == 0
    assert _walls(house, capsys) == []
    assert main(["level", "delete", str(house), "Primo piano"]) == 0


def test_top_and_height_are_exclusive(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        _add(house, "--top", "Primo piano", "--height", "3")
    assert info.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


def test_top_is_required(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        _add(house)
    assert info.value.code == 2
    assert "one of the arguments --top --height is required" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--top", "Soffitta"], "no level named 'Soffitta'"),
        (["--height", "3", "--top-offset", "0.1"], "top offset needs a top level"),
        (["--height", "0"], "must be above base"),
    ],
)
def test_add_errors(
    house: Path, capsys: pytest.CaptureFixture[str], extra: list[str], message: str
) -> None:
    before = house.read_bytes()
    capsys.readouterr()
    assert _add(house, *extra) == 1
    assert message in capsys.readouterr().err
    assert house.read_bytes() == before


def test_unknown_or_ambiguous_wall(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()
    assert main(["wall", "delete", str(house), "abcd"]) == 1
    assert "no wall with id 'abcd'" in capsys.readouterr().err


def test_list_and_info(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()
    assert main(["wall", "list", str(house)]) == 0
    assert capsys.readouterr().out.strip() == "no walls"
    _add(house, "--top", "Primo piano")
    capsys.readouterr()
    assert main(["wall", "list", str(house)]) == 0
    assert "base 'Piano terra', top 'Primo piano'" in capsys.readouterr().out
    assert main(["info", str(house)]) == 0
    assert "walls:   1" in capsys.readouterr().out


def test_schema_output_file(tmp_path: Path) -> None:
    out = tmp_path / "s.json"
    assert main(["schema", "--schema-version", "1", "-o", str(out)]) == 0
    assert json.loads(out.read_text("utf-8")) == api.json_schema(1)
    assert b"\r\n" not in out.read_bytes()
    assert main(["schema", "--schema-version", "9"]) == 1


def test_negative_decimal_comma(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """argparse alone would take -0,20 for an option; bbim reads it as -0.20."""
    assert main(["level", "add", str(house), "Interrato", "-2,80"]) == 0
    assert _add(house, "--base-offset", "-0,15", "--top", "Primo piano", "--top-offset", "-,2") == 0
    (row,) = _walls(house, capsys)
    assert (row["base_offset"], row["top_offset"]) == (-0.15, -0.2)
