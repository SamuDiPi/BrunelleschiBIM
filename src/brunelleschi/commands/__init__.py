"""Commands: the only code allowed to change a ``Project``.

Every change runs inside a ``transaction``. When the transaction ends the project's
invariants are checked; if a check fails, or the code inside raises, the project is
restored exactly as it was and the error propagates. A failed command never leaves a
half-applied change.
"""

from brunelleschi.commands.levels import (
    add_level,
    delete_level,
    rename_level,
    set_level_elevation,
)
from brunelleschi.commands.transaction import transaction
from brunelleschi.commands.walls import add_wall, delete_wall, modify_wall

__all__ = [
    "add_level",
    "add_wall",
    "delete_level",
    "delete_wall",
    "modify_wall",
    "rename_level",
    "set_level_elevation",
    "transaction",
]
