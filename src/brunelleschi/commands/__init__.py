"""Commands: the only code allowed to change a ``Project``.

Every change runs inside a ``transaction``. When the transaction ends the project's
invariants are checked; if a check fails, or the code inside raises, the project is
restored exactly as it was and the error propagates. A failed command never leaves a
half-applied change.
"""

from brunelleschi.commands.hosted import add_door, add_window, delete_hosted, modify_hosted
from brunelleschi.commands.levels import (
    add_level,
    delete_level,
    rename_level,
    set_level_elevation,
)
from brunelleschi.commands.references import add_reference, remove_reference
from brunelleschi.commands.transaction import transaction
from brunelleschi.commands.undo import (
    can_redo,
    can_undo,
    clear_history,
    current_step,
    redo,
    redo_label,
    undo,
    undo_label,
)
from brunelleschi.commands.walls import (
    add_wall,
    delete_wall,
    modify_wall,
    move_wall,
    move_wall_end,
)

__all__ = [
    "add_door",
    "add_level",
    "add_reference",
    "add_wall",
    "add_window",
    "can_redo",
    "can_undo",
    "clear_history",
    "current_step",
    "delete_hosted",
    "delete_level",
    "delete_wall",
    "modify_hosted",
    "modify_wall",
    "move_wall",
    "move_wall_end",
    "redo",
    "redo_label",
    "remove_reference",
    "rename_level",
    "set_level_elevation",
    "transaction",
    "undo",
    "undo_label",
]
