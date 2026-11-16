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

__all__ = ["add_level", "delete_level", "rename_level", "set_level_elevation", "transaction"]
