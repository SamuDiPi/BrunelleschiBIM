"""Snapping and picking in the plan (pure functions, no Qt)."""

from __future__ import annotations

import pytest

from brunelleschi import api
from brunelleschi.gui.snap import along_wall, grip_at, pick, snap


@pytest.fixture
def room() -> api.Project:
    p = api.new_project("Room")
    api.add_level(p, "G", 0.0)
    api.add_level(p, "F", 3.0)
    corners = [(0, 0), (6, 0), (6, 4), (0, 4)]
    for i, c in enumerate(corners):
        api.add_wall(p, c, corners[(i + 1) % 4], 0.3, "G", top_level="F")
    api.add_door(p, p.walls[0].id, 1.5, 0.9, 2.1)
    return p


def test_endpoint_wins(room: api.Project) -> None:
    s = snap(room, (6.07, 3.95), tolerance=0.2)
    assert (s.point, s.kind) == ((6.0, 4.0), "endpoint")


def test_on_wall(room: api.Project) -> None:
    s = snap(room, (3.03, 0.12), tolerance=0.2)
    assert s.kind == "on wall"
    assert s.point == (3.0, 0.0)  # exactly on the wall, on the grid along it
    assert s.wall == room.walls[0].id
    free = snap(room, (3.03, 0.12), tolerance=0.2, grid=None)
    assert free.point == pytest.approx((3.03, 0.0))


def test_grid(room: api.Project) -> None:
    s = snap(room, (2.04, 2.27), tolerance=0.2)
    assert (s.point, s.kind) == ((2.0, 2.3), "grid")
    free = snap(room, (2.04, 2.27), tolerance=0.2, grid=None)
    assert (free.point, free.kind) == ((2.04, 2.27), "free")


def test_ortho(room: api.Project) -> None:
    s = snap(room, (4.33, 2.52), tolerance=0.2, anchor=(2.05, 2.0), ortho=True)
    assert s.point == pytest.approx((4.3, 2.0))  # horizontal through the anchor, x on grid
    v = snap(room, (2.3, 3.4), tolerance=0.2, anchor=(2.05, 2.0), ortho=True)
    assert v.point == pytest.approx((2.05, 3.4))
    # An endpoint still wins over ortho.
    e = snap(room, (5.95, 0.4), tolerance=0.5, anchor=(2.0, 2.0), ortho=True)
    assert (e.point, e.kind) == ((6.0, 0.0), "endpoint")


def test_ortho_onto_a_wall(room: api.Project) -> None:
    # Drawing horizontally from (2, 2) towards the east wall lands exactly on it.
    s = snap(room, (5.93, 2.06), tolerance=0.2, anchor=(2.0, 2.0), ortho=True)
    assert s.kind == "on wall"
    assert s.point == pytest.approx((6.0, 2.0))


def test_exclude(room: api.Project) -> None:
    east = room.walls[1]
    s = snap(room, (6.02, 2.0), tolerance=0.2, exclude=frozenset({east.id}))
    assert s.kind == "grid"


def test_pick(room: api.Project) -> None:
    g = room.level("G").id
    door = room.doors[0]
    assert pick(room, (1.5, 0.0), tolerance=0.1, level=g) == door.id  # openings first
    assert pick(room, (4.0, 0.1), tolerance=0.1, level=g) == room.walls[0].id
    assert pick(room, (4.0, 0.3), tolerance=0.2, level=g) == room.walls[0].id  # near the line
    assert pick(room, (3.0, 2.0), tolerance=0.1, level=g) is None
    assert pick(room, (4.0, 0.1), tolerance=0.1, level=room.level("F").id) is None


def test_along_wall_and_side(room: api.Project) -> None:
    south = room.walls[0]  # (0,0) -> (6,0); left is +y, the room
    distance, side = along_wall(south, (2.5, 0.1))
    assert distance == pytest.approx(2.5)
    assert side == "left"
    assert along_wall(south, (2.5, -0.1))[1] == "right"


def test_grips(room: api.Project) -> None:
    south = room.walls[0]
    assert grip_at(south, (0.05, 0.0), 0.1) == "start"
    assert grip_at(south, (5.95, 0.02), 0.1) == "end"
    assert grip_at(south, (3.0, 0.0), 0.1) is None
