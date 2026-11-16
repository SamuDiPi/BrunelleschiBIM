"""Moving walls and wall ends; joined ends follow by default."""

from __future__ import annotations

import pytest

from brunelleschi import api


@pytest.fixture
def room() -> api.Project:
    p = api.new_project("Room")
    api.add_level(p, "G", 0.0)
    api.add_level(p, "F", 3.0)
    corners = [(0, 0), (6, 0), (6, 4), (0, 4)]
    for i, c in enumerate(corners):
        api.add_wall(p, c, corners[(i + 1) % 4], 0.3, "G", top_level="F")
    api.clear_history(p)
    return p


def kinds(p: api.Project) -> list[str]:
    return sorted(str(j.kind) for j in api.wall_geometry(p).joins)


def test_moving_a_corner_keeps_it_joined(room: api.Project) -> None:
    east, north = room.walls[1], room.walls[2]
    api.move_wall_end(room, east.id, "end", (7, 5))
    assert east.end == api.Point(7, 5)
    assert north.start == api.Point(7, 5)  # the joined end followed
    assert kinds(room) == ["mitre"] * 4
    assert api.undo_label(room) == "Move wall end"
    api.undo(room)
    assert (east.end, north.start) == (api.Point(6, 4), api.Point(6, 4))


def test_moving_a_corner_alone(room: api.Project) -> None:
    east, north = room.walls[1], room.walls[2]
    api.move_wall_end(room, east.id, "end", (7, 5), drag_joined=False)
    assert north.start == api.Point(6, 4)
    assert kinds(room) == ["mitre"] * 3  # that corner is open now; the other three are not


def test_moving_a_wall_stretches_its_neighbours(room: api.Project) -> None:
    south, east, _, west = room.walls
    api.move_wall(room, south.id, 0, -1)
    assert (south.start, south.end) == (api.Point(0, -1), api.Point(6, -1))
    assert east.start == api.Point(6, -1)
    assert west.end == api.Point(0, -1)
    assert kinds(room) == ["mitre"] * 4
    assert api.undo(room) == "Move wall"
    assert east.start == api.Point(6, 0)


def test_doors_move_with_their_wall(room: api.Project) -> None:
    south = room.walls[0]
    door = api.add_door(room, south.id, 1.5, 0.9, 2.1)
    api.move_wall(room, south.id, 2, 0, drag_joined=False)
    assert door.position == 1.5  # still 1.5 m from the (moved) start
    o = api.wall_geometry(room).openings[door.id]
    assert min(c[0] for c in o.corners) == pytest.approx(3.05)


def test_a_move_that_breaks_the_model_is_refused_whole(room: api.Project) -> None:
    east, north = room.walls[1], room.walls[2]
    with pytest.raises(api.ModelError, match="same point"):
        api.move_wall_end(room, east.id, "end", (6, 0))  # onto its own start
    assert (east.end, north.start) == (api.Point(6, 4), api.Point(6, 4))
    assert not api.can_undo(room)


def test_bad_end_name(room: api.Project) -> None:
    with pytest.raises(api.ModelError, match="'start' or 'end'"):
        api.move_wall_end(room, room.walls[0].id, "middle", (1, 1))
