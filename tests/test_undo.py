"""Undo and redo: one step per transaction, exact restoration, identity, random walks."""

from __future__ import annotations

import contextlib
import random
from collections.abc import Callable, Sequence
from typing import TypeVar

import pytest

from brunelleschi import api
from brunelleschi.commands.transaction import history
from brunelleschi.errors import BrunelleschiError, ModelError


@pytest.fixture
def project() -> api.Project:
    p = api.new_project("House")
    api.add_level(p, "Ground floor", 0.0)
    api.add_level(p, "First floor", 3.0)
    api.clear_history(p)
    return p


def wall(p: api.Project) -> api.Wall:
    return api.add_wall(p, (0, 0), (6, 0), 0.3, "Ground floor", top_level="First floor")


# --------------------------------------------------------------- basics


def test_new_and_loaded_projects_have_no_history(project: api.Project) -> None:
    fresh = api.new_project("P")
    assert not api.can_undo(fresh)
    assert api.undo(fresh) is None
    assert api.redo(fresh) is None
    loaded = api.loads(api.dumps(project))
    assert not api.can_undo(loaded)


def test_undo_and_redo_a_command(project: api.Project) -> None:
    w = wall(project)
    assert api.undo_label(project) == "Add wall"
    assert api.undo(project) == "Add wall"
    assert project.walls == []
    assert api.can_redo(project)
    assert api.redo_label(project) == "Add wall"
    assert api.redo(project) == "Add wall"
    assert project.walls == [w]
    assert project.walls[0] is w  # the same object comes back


def test_labels(project: api.Project) -> None:
    api.add_level(project, "Roof", 6.0)
    assert api.undo_label(project) == "Add level 'Roof'"
    w = wall(project)
    api.add_door(project, w.id, 1.0, 0.9, 2.1)
    assert api.undo_label(project) == "Add door"
    api.set_level_elevation(project, "Roof", 6.5)
    assert api.undo_label(project) == "Change level elevation"


def test_a_transaction_is_one_step(project: api.Project) -> None:
    with api.transaction(project, "Build a room"):
        corners = [(0, 0), (6, 0), (6, 4), (0, 4)]
        for i, c in enumerate(corners):
            api.add_wall(project, c, corners[(i + 1) % 4], 0.3, "Ground floor", height=3)
    assert len(project.walls) == 4
    assert api.undo(project) == "Build a room"
    assert project.walls == []
    assert not api.can_undo(project)


def test_unlabelled_transaction_takes_its_first_command(project: api.Project) -> None:
    with api.transaction(project):
        wall(project)
        api.add_level(project, "Roof", 6.0)
    assert api.undo_label(project) == "Add wall"


def test_failed_and_empty_changes_leave_no_step(project: api.Project) -> None:
    with pytest.raises(ModelError):
        api.add_level(project, "ground floor", 1.0)
    api.rename_level(project, "Ground floor", "Ground floor")  # no change
    with api.transaction(project):
        pass
    assert not api.can_undo(project)


def test_new_change_clears_redo(project: api.Project) -> None:
    wall(project)
    api.undo(project)
    assert api.can_redo(project)
    api.add_level(project, "Roof", 6.0)
    assert not api.can_redo(project)
    assert api.redo(project) is None


def test_cannot_undo_inside_a_transaction(project: api.Project) -> None:
    wall(project)
    with pytest.raises(ModelError, match="inside a transaction"), api.transaction(project):
        api.undo(project)
    assert len(project.walls) == 1


# ------------------------------------------------------- what comes back


def test_undo_modify_restores_values_on_the_same_objects(project: api.Project) -> None:
    w = wall(project)
    level = project.level("First floor")
    api.modify_wall(project, w.id, end=(9, 0), thickness=0.4, top_offset=-0.2)
    api.set_level_elevation(project, "First floor", 3.2)
    api.undo(project)
    assert level.elevation == 3.0
    api.undo(project)
    assert (w.end, w.thickness, w.top) == (api.Point(6, 0), 0.3, api.TopAtLevel(level.id, 0.0))
    api.redo(project)
    assert (w.end, w.thickness) == (api.Point(9, 0), 0.4)


def test_undo_delete_puts_elements_back_in_place(project: api.Project) -> None:
    a = wall(project)
    b = api.add_wall(project, (6, 0), (6, 4), 0.3, "Ground floor", height=3)
    c = api.add_wall(project, (6, 4), (0, 4), 0.3, "Ground floor", height=3)
    door = api.add_door(project, b.id, 2.0, 0.9, 2.1)
    before = api.dumps(project)
    api.delete_wall(project, b.id)  # also deletes the door, in the same step
    assert project.walls == [a, c]
    assert project.hosted == []
    api.undo(project)
    assert project.walls == [a, b, c]  # in its original position, so the file is the same
    assert project.hosted == [door]
    assert project.walls[1] is b and project.hosted[0] is door
    assert api.dumps(project) == before


def test_undo_restores_derived_geometry(project: api.Project) -> None:
    a = wall(project)
    api.add_wall(project, (0, 0), (0, 4), 0.3, "Ground floor", top_level="First floor")
    assert [str(j.kind) for j in api.wall_geometry(project).joins] == ["mitre"]
    api.modify_wall(project, a.id, start=(1, 1))
    assert api.wall_geometry(project).joins == ()
    api.undo(project)
    assert [str(j.kind) for j in api.wall_geometry(project).joins] == ["mitre"]


def test_undo_level_move_moves_walls_back(project: api.Project) -> None:
    w = wall(project)
    api.set_level_elevation(project, "First floor", 3.5)
    assert project.wall_z_range(w)[1] == 3.5
    api.undo(project)
    assert project.wall_z_range(w)[1] == 3.0


# ------------------------------------------------------------ random walks

Operation = Callable[[api.Project, random.Random], object]
T = TypeVar("T")


def _pick(rng: random.Random, items: Sequence[T]) -> T | None:
    return rng.choice(items) if items else None


def _op_add_level(p: api.Project, rng: random.Random) -> object:
    return api.add_level(p, rng.choice(["A", "B", "C", "D", "a"]), rng.choice([0, 3, 6, -3]))


def _op_move_level(p: api.Project, rng: random.Random) -> object:
    lv = _pick(rng, list(p.levels))
    assert isinstance(lv, api.Level)
    return api.set_level_elevation(p, lv.id, rng.choice([-1.0, 0.0, 2.5, 3.0, 4.0, 9.0]))


def _op_rename_level(p: api.Project, rng: random.Random) -> object:
    lv = _pick(rng, list(p.levels))
    assert isinstance(lv, api.Level)
    return api.rename_level(p, lv.id, rng.choice(["A", "B", "X", "Y", "Ground floor"]))


def _op_delete_level(p: api.Project, rng: random.Random) -> object:
    lv = _pick(rng, list(p.levels))
    assert isinstance(lv, api.Level)
    return api.delete_level(p, lv.id)


CORNERS = [(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0), (3.0, 0.0), (3.0, 4.0)]


def _point(rng: random.Random) -> tuple[float, float]:
    return rng.choice(CORNERS)


def _op_add_wall(p: api.Project, rng: random.Random) -> object:
    levels = sorted(p.levels, key=lambda lv: lv.elevation)
    base = _pick(rng, levels)
    assert isinstance(base, api.Level)
    above = [lv for lv in levels if lv.elevation > base.elevation]
    start, end = _point(rng), _point(rng)
    if above and rng.random() < 0.6:
        top = rng.choice(above) if rng.random() < 0.9 else base  # sometimes invalid
        return api.add_wall(p, start, end, 0.3, base.id, top_level=top.id)
    height = rng.choice([2.7, 3.0, 3.0, 0.0])  # 0 is invalid on purpose
    return api.add_wall(p, start, end, 0.2, base.id, height=height)


def _op_modify_wall(p: api.Project, rng: random.Random) -> object:
    w = _pick(rng, list(p.walls))
    assert isinstance(w, api.Wall)
    return api.modify_wall(
        p, w.id, end=_point(rng), thickness=rng.choice([None, 0.1, 0.5]), base_offset=0.1
    )


def _op_delete_wall(p: api.Project, rng: random.Random) -> object:
    w = _pick(rng, list(p.walls))
    assert isinstance(w, api.Wall)
    return api.delete_wall(p, w.id)


def _op_add_opening(p: api.Project, rng: random.Random) -> object:
    w = _pick(rng, list(p.walls))
    assert isinstance(w, api.Wall)
    position = round(rng.uniform(0.5, max(0.5, w.length - 0.5)), 1)
    if rng.random() < 0.5:
        return api.add_door(p, w.id, position, 0.8, 2.1, swing_side=rng.choice(["left", "right"]))
    return api.add_window(p, w.id, position, 0.8, 1.0, 1.0)


def _op_modify_opening(p: api.Project, rng: random.Random) -> object:
    e = _pick(rng, list(p.hosted))
    assert isinstance(e, api.HostedElement)
    return api.modify_hosted(
        p, e.id, position=rng.choice([0.5, 1.5, 3.0]), width=rng.choice([0.7, 0.9])
    )


def _op_delete_opening(p: api.Project, rng: random.Random) -> object:
    e = _pick(rng, list(p.hosted))
    assert isinstance(e, api.HostedElement)
    return api.delete_hosted(p, e.id)


def _op_batch(p: api.Project, rng: random.Random) -> object:
    with api.transaction(p, "Batch"):
        for _ in range(rng.randint(2, 4)):
            _run(p, rng, [op for op in OPERATIONS if op is not _op_batch])
    return None


# Weighted towards building, so that sequences reach walls with doors and windows.
OPERATIONS: list[Operation] = [
    _op_add_level,
    _op_move_level,
    _op_rename_level,
    _op_delete_level,
    *[_op_add_wall] * 4,
    *[_op_modify_wall] * 2,
    _op_delete_wall,
    *[_op_add_opening] * 4,
    *[_op_modify_opening] * 2,
    _op_delete_opening,
    _op_batch,
]


def _run(p: api.Project, rng: random.Random, operations: list[Operation]) -> None:
    # Invalid on purpose, or nothing to act on: either way it must leave no trace.
    with contextlib.suppress(BrunelleschiError, AssertionError):
        rng.choice(operations)(p, rng)


def _state(p: api.Project) -> tuple[str, list[int]]:
    """The saved file, plus element identities (undo must bring back the same objects)."""
    ids = [id(e) for store in api.Project.STORES for e in getattr(p, store).values()]
    return api.dumps(p), ids


@pytest.mark.parametrize("seed", range(150))
def test_random_sequences_undo_and_redo_exactly(seed: int) -> None:
    rng = random.Random(seed)
    p = api.new_project("Random")
    api.add_level(p, "Ground floor", 0.0)
    api.add_level(p, "First floor", 3.0)
    api.clear_history(p)

    # Build a history; remember the state after every recorded step.
    states = [_state(p)]
    for _ in range(40):
        _run(p, rng, OPERATIONS)
        if len(history(p).done) == len(states):  # this operation recorded a step
            states.append(_state(p))
        assert len(history(p).done) == len(states) - 1
        assert _state(p) == states[-1]  # a failed operation changed nothing

    # Undo everything, checking each intermediate state, then redo everything.
    for position in range(len(states) - 1, 0, -1):
        assert api.undo(p) is not None
        assert _state(p) == states[position - 1]
    assert api.undo(p) is None
    for position in range(1, len(states)):
        assert api.redo(p) is not None
        assert _state(p) == states[position]

    # A random walk of undos and redos never leaves the recorded states.
    position = len(states) - 1
    for _ in range(40):
        if rng.random() < 0.5 and position > 0:
            api.undo(p)
            position -= 1
        elif position < len(states) - 1:
            api.redo(p)
            position += 1
        assert _state(p) == states[position]
    p.check()
