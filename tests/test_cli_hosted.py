"""The ``bbim door``, ``bbim window`` and ``bbim check`` commands, end to end."""

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
    assert main(["level", "add", str(path), "Primo piano", "3"]) == 0
    args = ["wall", "add", str(path), "--start", "0", "0", "--end", "6", "0"]
    assert main([*args, "--thickness", "0,3", "--base", "Piano terra", "--top", "Primo piano"]) == 0
    return path


def _wall_id(house: Path) -> str:
    return api.short_id(api.load(house).walls[0].id)


def _list(house: Path, kind: str, capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    capsys.readouterr()
    assert main([kind, "list", str(house), "--json"]) == 0
    rows: list[dict[str, object]] = json.loads(capsys.readouterr().out)
    return rows


def test_add_door_and_window(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    w = _wall_id(house)
    door = ["door", "add", str(house), w, "--position", "1,20", "--width", "0,90"]
    assert main([*door, "--height", "2,10", "--swing", "right", "--hinge", "end"]) == 0
    assert "swings right, hinge at end" in capsys.readouterr().out
    window = ["window", "add", str(house), w, "--position", "4", "--width", "1,4"]
    assert main([*window, "--height", "1,2", "--sill", "0,9"]) == 0
    (d,) = _list(house, "door", capsys)
    assert (d["position"], d["width"], d["height"], d["sill_height"]) == (1.2, 0.9, 2.1, 0.0)
    assert d["swing"] == {"side": "right", "hinge": "end"}
    (win,) = _list(house, "window", capsys)
    assert (win["z_bottom"], win["z_top"]) == pytest.approx((0.9, 2.1))
    assert "swing" not in win
    capsys.readouterr()
    assert main(["info", str(house)]) == 0
    out = capsys.readouterr().out
    assert "doors:   1" in out
    assert "windows: 1" in out


def test_window_needs_a_sill(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ["window", "add", str(house), _wall_id(house), "--position", "3", "--width", "1"]
    with pytest.raises(SystemExit) as info:
        main([*args, "--height", "1"])
    assert info.value.code == 2
    assert "--sill" in capsys.readouterr().err


def test_door_that_does_not_fit(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    before = house.read_bytes()
    capsys.readouterr()
    args = ["door", "add", str(house), _wall_id(house), "--position", "5,8", "--width", "0,9"]
    assert main([*args, "--height", "2,1"]) == 1
    assert "does not fit" in capsys.readouterr().err
    assert house.read_bytes() == before


def test_modify_and_delete(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    w = _wall_id(house)
    main(["door", "add", str(house), w, "--position", "1", "--width", "0,9", "--height", "2,1"])
    door_id = str(_list(house, "door", capsys)[0]["id"])[:6]
    assert main(["door", "modify", str(house), door_id, "--position", "3", "--swing", "right"]) == 0
    (d,) = _list(house, "door", capsys)
    assert d["position"] == 3.0
    assert d["swing"] == {"side": "right", "hinge": "start"}
    # A door id is not a window.
    assert main(["window", "delete", str(house), door_id]) == 1
    assert "is a door, not a window" in capsys.readouterr().err
    assert main(["door", "delete", str(house), door_id]) == 0
    assert _list(house, "door", capsys) == []


def test_wall_move_keeps_door_and_shortening_is_refused(
    house: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    w = _wall_id(house)
    args = ["window", "add", str(house), w, "--position", "5", "--width", "1", "--height", "1"]
    assert main([*args, "--sill", "1"]) == 0
    capsys.readouterr()
    assert main(["window", "list", str(house)]) == 0
    assert f"in wall {w}" in capsys.readouterr().out
    assert main(["wall", "modify", str(house), w, "--end", "5", "0"]) == 1
    assert "does not fit" in capsys.readouterr().err
    assert main(["wall", "modify", str(house), w, "--end", "9", "0"]) == 0
    assert _list(house, "window", capsys)[0]["position"] == 5.0


def test_deleting_the_wall_deletes_the_door(
    house: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    w = _wall_id(house)
    main(["door", "add", str(house), w, "--position", "1", "--width", "0,9", "--height", "2,1"])
    capsys.readouterr()
    assert main(["wall", "delete", str(house), w]) == 0
    assert "and its door" in capsys.readouterr().out
    assert _list(house, "door", capsys) == []


def test_check(house: Path, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()
    assert main(["check", str(house)]) == 0
    assert capsys.readouterr().out.strip() == "no warnings"
    args = ["wall", "add", str(house), "--start", "3", "0", "--end", "3", "4"]
    main([*args, "--thickness", "0,12", "--base", "Piano terra", "--top", "Primo piano"])
    w = _wall_id(house)
    main(["door", "add", str(house), w, "--position", "3", "--width", "0,9", "--height", "2,1"])
    capsys.readouterr()
    assert main(["check", str(house)]) == 0
    assert "is blocked by wall" in capsys.readouterr().out
