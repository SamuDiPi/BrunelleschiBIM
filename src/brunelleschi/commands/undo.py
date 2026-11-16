"""Undo and redo.

Every committed transaction is one step. The history lives in memory with the project
object: it is empty for a project just created or loaded, and it is not saved in the
file. A new change after some undos discards the steps that could have been redone.
"""

from __future__ import annotations

from brunelleschi.commands.transaction import history, in_transaction
from brunelleschi.errors import ModelError
from brunelleschi.model import Project


def _not_in_transaction(project: Project, action: str) -> None:
    if in_transaction(project):
        raise ModelError(f"cannot {action} inside a transaction")


def undo(project: Project) -> str | None:
    """Undo the last step; return its label, or None if there was nothing to undo."""
    _not_in_transaction(project, "undo")
    h = history(project)
    if not h.done:
        return None
    step = h.done.pop()
    step.apply(project, forward=False)
    h.undone.append(step)
    return step.label


def redo(project: Project) -> str | None:
    """Redo the last undone step; return its label, or None if there was nothing to redo."""
    _not_in_transaction(project, "redo")
    h = history(project)
    if not h.undone:
        return None
    step = h.undone.pop()
    step.apply(project, forward=True)
    h.done.append(step)
    return step.label


def can_undo(project: Project) -> bool:
    return bool(history(project).done)


def can_redo(project: Project) -> bool:
    return bool(history(project).undone)


def undo_label(project: Project) -> str | None:
    """Label of the step ``undo`` would undo, for a menu entry such as "Undo Add wall"."""
    done = history(project).done
    return done[-1].label if done else None


def redo_label(project: Project) -> str | None:
    undone = history(project).undone
    return undone[-1].label if undone else None


def clear_history(project: Project) -> None:
    """Forget every step (for example after saving, if the interface wants that)."""
    h = history(project)
    h.done.clear()
    h.undone.clear()
