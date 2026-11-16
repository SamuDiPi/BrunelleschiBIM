"""Atomic changes with invariant checks at commit.

The rollback strategy is a snapshot of the project taken when the outermost transaction
starts. That is simple and obviously correct for small models; when models grow it will
be replaced by recorded inverse operations, which will also give undo/redo. The public
behaviour stays the same.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from brunelleschi.model import Level, Project

# Projects with an open transaction, by identity. Nested transactions join the outer one.
_open: set[int] = set()


@contextmanager
def transaction(project: Project) -> Iterator[Project]:
    """Run a group of changes atomically.

    >>> with transaction(project):
    ...     add_level(project, "Level 1", 3.0)
    ...     add_level(project, "Level 2", 6.0)

    Either both levels exist afterwards, or (if anything failed) neither does.
    """
    key = id(project)
    if key in _open:  # nested: the outer transaction checks and rolls back
        yield project
        return

    snapshot = _Snapshot(project)
    _open.add(key)
    try:
        yield project
        project.check()
    except BaseException:
        snapshot.restore(project)
        raise
    finally:
        _open.discard(key)


class _Snapshot:
    """The state of a project, kept so that it can be put back in place.

    Restoring keeps the identity of the project and of every element that existed when
    the snapshot was taken, so references held by callers see the old values again.
    """

    def __init__(self, project: Project) -> None:
        self.name = project.name
        self.levels: dict[UUID, Level] = dict(project._levels)  # original objects, in order
        self.values: dict[UUID, Level] = {k: copy.copy(v) for k, v in project._levels.items()}

    def restore(self, project: Project) -> None:
        project.name = self.name
        for level_id, level in self.levels.items():
            saved = self.values[level_id]
            level.name, level.elevation = saved.name, saved.elevation
        project._levels = dict(self.levels)
