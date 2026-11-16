"""Start the BrunelleschiBIM desktop application.

bbim-gui [PROJECT.bbim]
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from brunelleschi.gui.document import Document
from brunelleschi.gui.main_window import MainWindow

USAGE = "usage: bbim-gui [PROJECT.bbim]"


def parse_args(argv: Sequence[str]) -> Path | str | None:
    """The project to open, None for a new one, or an error message.

    Anything unexpected is refused before a window exists: in a packaged build a library
    may relaunch the program with its own arguments (ADR 0009), and that must not open a
    second window.
    """
    if not argv:
        return None
    if len(argv) == 1 and argv[0].lower().endswith(".bbim") and not argv[0].startswith("-"):
        return Path(argv[0])
    return f"{USAGE}\nunexpected arguments: {' '.join(argv)}"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    parsed = parse_args(args)
    if isinstance(parsed, str):
        print(parsed, file=sys.stderr)
        return 2
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("BrunelleschiBIM")
    window = MainWindow(Document())
    if parsed is not None:
        window.open_file(parsed)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
