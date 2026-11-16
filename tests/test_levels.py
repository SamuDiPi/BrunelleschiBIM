"""Levels: the model, the commands and transactions."""

from __future__ import annotations

import math
from uuid import uuid4

import pytest

from brunelleschi import api
from brunelleschi.errors import ModelError, NotFoundError


@pytest.fixture
def project() -> api.Project:
    p = api.new_project("House")
    api.add_level(p, "Ground floor", 0.0)
    api.add_level(p, "First floor", 3.0)
    return p


def test_new_project_is_empty() -> None:
    p = api.new_project("  House  ")
    assert p.name == "House"
    assert p.levels == []


def test_new_project_needs_a_name() -> None:
    with pytest.raises(ModelError, match="project name is empty"):
        api.new_project("   ")


def test_add_level(project: api.Project) -> None:
    level = api.add_level(project, "  Roof ", 6.5)
    assert level.name == "Roof"
    assert level.elevation == 6.5
    assert [lv.name for lv in project.levels] == ["Ground floor", "First floor", "Roof"]
    assert project.level(level.id) is level


def test_add_level_with_given_id(project: api.Project) -> None:
    wanted = uuid4()
    assert api.add_level(project, "Roof", 6.0, level_id=wanted).id == wanted


def test_levels_by_elevation(project: api.Project) -> None:
    api.add_level(project, "Basement", -3.0)
    names = [lv.name for lv in project.levels_by_elevation()]
    assert names == ["Basement", "Ground floor", "First floor"]


def test_lookup_by_name_ignores_case_and_spaces(project: api.Project) -> None:
    assert project.level("  first FLOOR ").name == "First floor"


def test_lookup_of_missing_level(project: api.Project) -> None:
    with pytest.raises(NotFoundError, match="no level named 'Attic'"):
        project.level("Attic")
    with pytest.raises(NotFoundError, match="no level with id"):
        project.level(uuid4())


@pytest.mark.parametrize("name", ["First floor", "FIRST FLOOR", " first floor "])
def test_duplicate_name_is_refused(project: api.Project, name: str) -> None:
    with pytest.raises(ModelError, match="unique"):
        api.add_level(project, name, 9.0)
    assert len(project.levels) == 2


@pytest.mark.parametrize("bad", ["", "   ", "x" * 201])
def test_bad_name_is_refused(project: api.Project, bad: str) -> None:
    with pytest.raises(ModelError):
        api.add_level(project, bad, 9.0)
    assert len(project.levels) == 2


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 1e7, -1e7])
def test_bad_elevation_is_refused(project: api.Project, bad: float) -> None:
    with pytest.raises(ModelError):
        api.add_level(project, "Roof", bad)
    with pytest.raises(ModelError):
        api.set_level_elevation(project, "First floor", bad)
    assert project.level("First floor").elevation == 3.0


def test_rename_level(project: api.Project) -> None:
    level = project.level("First floor")
    api.rename_level(project, "first floor", "Level 1")
    assert level.name == "Level 1"
    with pytest.raises(NotFoundError):
        project.level("First floor")


def test_rename_to_the_same_name_with_other_case(project: api.Project) -> None:
    api.rename_level(project, "First floor", "FIRST FLOOR")
    assert project.level("first floor").name == "FIRST FLOOR"


def test_rename_onto_another_level_rolls_back(project: api.Project) -> None:
    level = project.level("First floor")
    with pytest.raises(ModelError, match="unique"):
        api.rename_level(project, "First floor", "ground floor")
    # The caller's reference sees the old value again.
    assert level.name == "First floor"


def test_move_level(project: api.Project) -> None:
    api.set_level_elevation(project, "First floor", 3.2)
    assert project.level("First floor").elevation == 3.2


def test_delete_level(project: api.Project) -> None:
    deleted = api.delete_level(project, "Ground floor")
    assert deleted.name == "Ground floor"
    assert [lv.name for lv in project.levels] == ["First floor"]
    with pytest.raises(NotFoundError):
        api.delete_level(project, "Ground floor")


def test_transaction_is_all_or_nothing(project: api.Project) -> None:
    ground = project.level("Ground floor")
    with pytest.raises(ModelError), api.transaction(project):
        api.add_level(project, "Roof", 6.0)
        api.set_level_elevation(project, ground.id, -1.0)
        api.delete_level(project, "First floor")
        api.add_level(project, "roof", 9.0)  # duplicate: everything is undone
    assert [lv.name for lv in project.levels] == ["Ground floor", "First floor"]
    assert ground.elevation == 0.0
    assert project.levels[0] is ground


def test_transaction_rolls_back_on_any_exception(project: api.Project) -> None:
    with pytest.raises(RuntimeError), api.transaction(project):
        api.add_level(project, "Roof", 6.0)
        raise RuntimeError("boom")
    assert len(project.levels) == 2


def test_transaction_checks_only_at_commit(project: api.Project) -> None:
    # A swap of two names passes through a state with a duplicate; that is allowed.
    with api.transaction(project):
        api.rename_level(project, "Ground floor", "Temporary")
        api.rename_level(project, "First floor", "Ground floor")
        api.rename_level(project, "Temporary", "First floor")
    assert project.level("Ground floor").elevation == 3.0


def test_transaction_can_be_reused_after_failure(project: api.Project) -> None:
    with pytest.raises(ModelError):
        api.add_level(project, "first floor", 1.0)
    api.add_level(project, "Roof", 6.0)
    assert len(project.levels) == 3
