"""Atomic changes with invariant checks at commit, and the undo history they feed.

When the outermost transaction starts, the project is snapshotted (the element objects
and a copy of their fields). If anything fails, the snapshot is restored in place. If the
transaction commits, the difference between the snapshot and the new state becomes one
step of the project's undo history: only the elements added, removed or changed, plus
the element order when membership changed. Undo and redo apply such a step backwards or
forwards, keeping the identity of every element object, so references held by scripts or
by the interface stay valid.
"""

from __future__ import annotations

import copy
import weakref
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from typing import Any
from uuid import UUID

from brunelleschi.model import Project

# Projects with an open transaction, by identity, with the label of the outermost one.
# Nested transactions join the outer one.
_open: dict[int, list[str | None]] = {}


@contextmanager
def transaction(project: Project, label: str | None = None) -> Iterator[Project]:
    """Run a group of changes atomically, as one undo step.

    >>> with transaction(project, "Add two levels"):
    ...     add_level(project, "Level 1", 3.0)
    ...     add_level(project, "Level 2", 6.0)

    Either both levels exist afterwards, or (if anything failed) neither does. Undo
    removes both at once. Without a label, the step takes the label of the first command
    run inside it.
    """
    key = id(project)
    if key in _open:  # nested: the outer transaction checks, rolls back and records
        if _open[key][0] is None:
            _open[key][0] = label
        yield project
        return

    snapshot = _Snapshot(project)
    _open[key] = [label]
    try:
        yield project
        project.check()
    except BaseException:
        snapshot.restore(project)
        raise
    else:
        step = snapshot.difference(project, _open[key][0] or "Change")
        if step is not None:
            history(project).record(step)
    finally:
        _open.pop(key, None)


def in_transaction(project: Project) -> bool:
    return id(project) in _open


# ------------------------------------------------------------------ snapshot


def _assign(element: Any, values: Any) -> None:
    for f in fields(element):
        setattr(element, f.name, getattr(values, f.name))


class _Snapshot:
    """The state of a project, kept so that it can be put back in place.

    Field values of elements are immutable (numbers, strings, ids, enums, frozen
    dataclasses), so a shallow copy of each element is a full copy of its state.
    """

    def __init__(self, project: Project) -> None:
        self.name = project.name
        self.stores: dict[str, dict[UUID, Any]] = {}
        self.values: dict[str, dict[UUID, Any]] = {}
        for store in Project.STORES:
            elements: dict[UUID, Any] = getattr(project, store)
            self.stores[store] = dict(elements)  # the original objects, in order
            self.values[store] = {k: copy.copy(v) for k, v in elements.items()}

    def restore(self, project: Project) -> None:
        project.name = self.name
        for store, originals in self.stores.items():
            for element_id, element in originals.items():
                _assign(element, self.values[store][element_id])
            setattr(project, store, dict(originals))

    def difference(self, project: Project, label: str) -> Step | None:
        """What changed since the snapshot, or None if nothing did."""
        changes: list[_StoreChange] = []
        for store in Project.STORES:
            before_objects = self.stores[store]
            before_values = self.values[store]
            after: dict[UUID, Any] = getattr(project, store)
            change = _StoreChange(store)
            for element_id, element in after.items():
                if element_id not in before_objects:
                    change.added[element_id] = (element, copy.copy(element))
                elif before_values[element_id] != element:
                    change.changed[element_id] = (
                        element,
                        before_values[element_id],
                        copy.copy(element),
                    )
            for element_id, element in before_objects.items():
                if element_id not in after:
                    change.removed[element_id] = (element, before_values[element_id])
            if change.added or change.removed:
                change.order_before = list(before_objects)
                change.order_after = list(after)
            if change.added or change.removed or change.changed:
                changes.append(change)
        if not changes and project.name == self.name:
            return None
        return Step(label, changes, (self.name, project.name))


# ------------------------------------------------------------------- history


@dataclass
class _StoreChange:
    store: str
    added: dict[UUID, tuple[Any, Any]] = field(default_factory=dict)  # object, values
    removed: dict[UUID, tuple[Any, Any]] = field(default_factory=dict)  # object, values
    changed: dict[UUID, tuple[Any, Any, Any]] = field(default_factory=dict)  # obj, old, new
    order_before: list[UUID] | None = None
    order_after: list[UUID] | None = None

    def apply(self, project: Project, forward: bool) -> None:
        elements: dict[UUID, Any] = getattr(project, self.store)
        for element, old, new in self.changed.values():
            _assign(element, new if forward else old)
        if self.order_before is None or self.order_after is None:
            return
        appearing = self.added if forward else self.removed
        for element, values in appearing.values():
            _assign(element, values)
        pool = {**elements, **{k: v[0] for k, v in appearing.items()}}
        order = self.order_after if forward else self.order_before
        setattr(project, self.store, {k: pool[k] for k in order})


@dataclass
class Step:
    """One undoable change: what one committed transaction did."""

    label: str
    changes: list[_StoreChange]
    names: tuple[str, str]  # project name before and after

    def apply(self, project: Project, forward: bool) -> None:
        project.name = self.names[1] if forward else self.names[0]
        for change in self.changes:
            change.apply(project, forward)


@dataclass
class History:
    """The undo and redo stacks of one project."""

    done: list[Step] = field(default_factory=list)
    undone: list[Step] = field(default_factory=list)

    def record(self, step: Step) -> None:
        self.done.append(step)
        self.undone.clear()


_histories: dict[int, tuple[weakref.ref[Project], History]] = {}


def history(project: Project) -> History:
    """The undo history of a project (empty for a project just created or loaded)."""
    key = id(project)
    entry = _histories.get(key)
    if entry is None or entry[0]() is not project:
        h = History()
        _histories[key] = (weakref.ref(project, lambda _: _histories.pop(key, None)), h)
        return h
    return entry[1]
