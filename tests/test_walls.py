"""Walls bound to levels: parameters, derived elevations, propagation and invariants."""

from __future__ import annotations

import math
from uuid import UUID

import pytest

from brunelleschi import api
from brunelleschi.errors import AmbiguousReferenceError, ModelError, NotFoundError


@pytest.fixture
def project() -> api.Project:
    p = api.new_project("House")
    api.add_level(p, "Ground floor", 0.0)
    api.add_level(p, "First floor", 3.0)
    api.add_level(p, "Second floor", 6.0)
    return p


def _wall(p: api.Project, **kw: object) -> api.Wall:
    args: dict[str, object] = {"top_level": "First floor"} | kw
    return api.add_wall(p, (0, 0), (5, 0), 0.3, "Ground floor", **args)  # type: ignore[arg-type]


def _z(p: api.Project, wall: api.Wall) -> tuple[float, float]:
    base, top = p.wall_z_range(wall)
    return round(base, 9), round(top, 9)


# ------------------------------------------------------------------ creation


def test_wall_to_top_level(project: api.Project) -> None:
    wall = _wall(project)
    assert wall.length == 5.0
    assert wall.thickness == 0.3
    assert wall.start == api.Point(0.0, 0.0)
    assert wall.top == api.TopAtLevel(project.level("First floor").id, 0.0)
    assert _z(project, wall) == (0.0, 3.0)
    assert project.walls == [wall]


def test_wall_with_offsets(project: api.Project) -> None:
    wall = _wall(project, base_offset=-0.4, top_offset=-0.25)
    assert _z(project, wall) == (-0.4, 2.75)


def test_wall_with_unconnected_height(project: api.Project) -> None:
    wall = api.add_wall(project, (0, 0), (0, 4), 0.2, "First floor", base_offset=0.1, height=1.1)
    assert wall.top == api.UnconnectedHeight(1.1)
    assert _z(project, wall) == (3.1, 4.2)


def test_length_of_a_diagonal_wall(project: api.Project) -> None:
    wall = api.add_wall(project, (1, 1), (4, 5), 0.3, "Ground floor", height=3)
    assert math.isclose(wall.length, 5.0)


def test_top_needs_exactly_one_definition(project: api.Project) -> None:
    with pytest.raises(ModelError, match="give a top level or a height"):
        api.add_wall(project, (0, 0), (5, 0), 0.3, "Ground floor")
    with pytest.raises(ModelError, match="not both"):
        _wall(project, height=3.0)
    with pytest.raises(ModelError, match="top offset needs a top level"):
        api.add_wall(project, (0, 0), (5, 0), 0.3, "Ground floor", height=3, top_offset=0.1)
    assert project.walls == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"end": (0, 0)}, "same point"),
        ({"end": (0, 1e-7)}, "same point"),
        ({"thickness": 0.0}, "thickness must be greater than zero"),
        ({"thickness": -0.3}, "thickness must be greater than zero"),
        ({"thickness": math.nan}, "thickness must be a finite number"),
        ({"start": (math.inf, 0)}, "start x must be a finite number"),
        ({"start": (0, 2e6)}, "start y must be a finite number"),
        ({"top_offset": -3.0}, "top .* must be above base"),
        ({"top_offset": -3.5}, "top .* must be above base"),
        ({"base_offset": 3.0}, "top .* must be above base"),
    ],
)
def test_invalid_walls_are_rejected_at_commit(
    project: api.Project, kwargs: dict[str, object], message: str
) -> None:
    args: dict[str, object] = {
        "start": (0, 0),
        "end": (5, 0),
        "thickness": 0.3,
        "base_level": "Ground floor",
        "top_level": "First floor",
    } | kwargs
    with pytest.raises(ModelError, match=message):
        api.add_wall(project, **args)  # type: ignore[arg-type]
    assert project.walls == []


def test_unconnected_height_must_be_positive(project: api.Project) -> None:
    for height in (0.0, -1.0):
        with pytest.raises(ModelError, match="must be above base"):
            api.add_wall(project, (0, 0), (5, 0), 0.3, "Ground floor", height=height)


def test_unknown_level_is_refused(project: api.Project) -> None:
    with pytest.raises(NotFoundError, match="Attic"):
        _wall(project, top_level="Attic")
    with pytest.raises(NotFoundError, match="Attic"):
        api.add_wall(project, (0, 0), (5, 0), 0.3, "Attic", height=3)


# ---------------------------------------------------------- level propagation


def test_moving_a_level_moves_exactly_the_bound_walls(project: api.Project) -> None:
    """The M2 acceptance test: every wall bound to the level follows it, no other does."""
    to_first = _wall(project)  # ground -> first
    from_first = api.add_wall(  # first -> second
        project, (0, 0), (5, 0), 0.3, "First floor", top_level="Second floor"
    )
    on_first = api.add_wall(project, (0, 5), (5, 5), 0.3, "First floor", height=1.0)
    elsewhere = api.add_wall(  # ground -> second: bound to neither end of "First floor"
        project, (9, 0), (9, 5), 0.3, "Ground floor", top_level="Second floor"
    )
    free = api.add_wall(project, (0, 9), (5, 9), 0.3, "Ground floor", height=2.4)

    before = {w.id: _z(project, w) for w in project.walls}
    api.set_level_elevation(project, "First floor", 3.3)
    after = {w.id: _z(project, w) for w in project.walls}

    assert after[to_first.id] == (0.0, 3.3)
    assert after[from_first.id] == (3.3, 6.0)
    assert after[on_first.id] == (3.3, 4.3)
    assert after[elsewhere.id] == before[elsewhere.id] == (0.0, 6.0)
    assert after[free.id] == before[free.id] == (0.0, 2.4)
    bound = {w.id for w in project.walls_on_level(project.level("First floor").id)}
    assert bound == {to_first.id, from_first.id, on_first.id}


def test_moving_a_level_that_would_invert_a_wall_is_refused(project: api.Project) -> None:
    wall = _wall(project)
    with pytest.raises(ModelError, match=f"wall {api.short_id(wall.id)}: top"):
        api.set_level_elevation(project, "First floor", -0.5)
    assert project.level("First floor").elevation == 3.0
    assert _z(project, wall) == (0.0, 3.0)


def test_moving_the_base_level_carries_unconnected_walls(project: api.Project) -> None:
    wall = api.add_wall(project, (0, 0), (5, 0), 0.3, "Ground floor", height=2.7)
    api.set_level_elevation(project, "Ground floor", -0.15)
    assert _z(project, wall) == (-0.15, 2.55)


# ------------------------------------------------------------- level deletion


def test_deleting_a_level_used_by_walls_is_refused(project: api.Project) -> None:
    a = _wall(project)
    b = api.add_wall(project, (0, 0), (5, 0), 0.3, "First floor", height=3)
    with pytest.raises(ModelError) as info:
        api.delete_level(project, "First floor")
    message = str(info.value)
    assert "cannot be deleted" in message
    assert api.short_id(a.id) in message
    assert api.short_id(b.id) in message
    assert len(project.levels) == 3


def test_level_can_be_deleted_once_its_walls_are_gone(project: api.Project) -> None:
    wall = _wall(project)
    api.delete_wall(project, wall.id)
    api.delete_level(project, "First floor")
    assert [lv.name for lv in project.levels] == ["Ground floor", "Second floor"]


# -------------------------------------------------------------------- modify


def test_modify_geometry(project: api.Project) -> None:
    wall = _wall(project)
    same = api.modify_wall(project, wall.id, start=(1, 1), end=(1, 4), thickness=0.25)
    assert same is wall
    assert (wall.start, wall.end, wall.thickness) == (api.Point(1, 1), api.Point(1, 4), 0.25)
    assert wall.length == 3.0


def test_modify_switches_between_top_level_and_height(project: api.Project) -> None:
    wall = _wall(project, top_offset=-0.2)
    api.modify_wall(project, wall.id, height=2.5)
    assert wall.top == api.UnconnectedHeight(2.5)
    assert _z(project, wall) == (0.0, 2.5)
    api.modify_wall(project, wall.id, top_level="Second floor")
    assert project.wall(wall.id).top == api.TopAtLevel(project.level("Second floor").id, 0.0)
    api.modify_wall(project, wall.id, top_offset=0.4)
    assert _z(project, wall) == (0.0, 6.4)
    # Changing the top level keeps the offset unless a new one is given.
    api.modify_wall(project, wall.id, top_level="First floor")
    assert _z(project, wall) == (0.0, 3.4)


def test_modify_base(project: api.Project) -> None:
    wall = _wall(project, top_level="Second floor")
    api.modify_wall(project, wall.id, base_level="First floor", base_offset=0.1)
    assert _z(project, wall) == (3.1, 6.0)
    assert wall.level_ids() == {project.level("First floor").id, project.level("Second floor").id}


def test_modify_top_offset_of_unconnected_wall_is_refused(project: api.Project) -> None:
    wall = api.add_wall(project, (0, 0), (5, 0), 0.3, "Ground floor", height=3)
    with pytest.raises(ModelError, match="not bound to a level"):
        api.modify_wall(project, wall.id, top_offset=0.2)
    with pytest.raises(ModelError, match="top offset needs a top level"):
        api.modify_wall(project, wall.id, height=2, top_offset=0.2)


def test_failed_modify_rolls_back_every_field(project: api.Project) -> None:
    wall = _wall(project)
    with pytest.raises(ModelError, match="must be above base"):
        api.modify_wall(project, wall.id, start=(2, 2), thickness=0.5, base_offset=4.0)
    assert wall.start == api.Point(0, 0)
    assert wall.thickness == 0.3
    assert wall.base_offset == 0.0
    assert project.walls == [wall]


def test_transaction_spanning_levels_and_walls(project: api.Project) -> None:
    """Raising a level above a wall's top is fine if the wall is fixed in the same step."""
    wall = api.add_wall(project, (0, 0), (5, 0), 0.3, "First floor", height=2.0)
    with api.transaction(project):
        api.modify_wall(project, wall.id, base_level="Ground floor")
        api.set_level_elevation(project, "First floor", 2.0)
    assert _z(project, wall) == (0.0, 2.0)


def test_rolled_back_delete_restores_the_same_wall(project: api.Project) -> None:
    wall = _wall(project)
    with pytest.raises(RuntimeError), api.transaction(project):
        api.delete_wall(project, wall.id)
        raise RuntimeError("boom")
    assert project.walls == [wall]
    assert project.walls[0] is wall


# ------------------------------------------------------------- short ids


def test_lookup_by_short_id(project: api.Project) -> None:
    wall = _wall(project, wall_id=UUID("3f2a91c0-1111-4111-8111-111111111111"))
    assert project.wall("3f2a91c0") is wall
    assert project.wall("3F2A") is wall
    assert project.wall(str(wall.id)) is wall
    assert api.short_id(wall.id) == "3f2a91c0"


def test_short_id_errors(project: api.Project) -> None:
    _wall(project, wall_id=UUID("3f2a91c0-1111-4111-8111-111111111111"))
    _wall(project, wall_id=UUID("3f2a77aa-2222-4222-8222-222222222222"))
    with pytest.raises(AmbiguousReferenceError, match="matches 2 walls"):
        project.wall("3f2a")
    with pytest.raises(NotFoundError, match="too short"):
        project.wall("3f2")
    with pytest.raises(NotFoundError, match="no wall"):
        project.wall("ffff")
    assert project.wall("3f2a9").id.hex.startswith("3f2a91c0")


def test_delete_wall(project: api.Project) -> None:
    wall = _wall(project)
    assert api.delete_wall(project, api.short_id(wall.id)) is wall
    assert project.walls == []
    with pytest.raises(NotFoundError):
        api.delete_wall(project, wall.id)
