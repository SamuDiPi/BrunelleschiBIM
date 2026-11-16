"""What happens when something goes wrong that nobody expected.

The packaged program has no console, so an unhandled error would otherwise vanish (or, at
start-up, show PyInstaller's own dialog). Here every such error is written to a log file
with the full traceback, and the user gets a short message saying where the log is.
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
import traceback
from pathlib import Path
from types import TracebackType


def log_folder() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "state")
    return Path(base) / "BrunelleschiBIM" / "logs"


def write_crash_log(
    kind: type[BaseException], value: BaseException, tb: TracebackType | None
) -> Path | None:
    """Write the traceback to a new log file; None if even that is impossible."""
    from brunelleschi import __version__

    try:
        folder = log_folder()
        folder.mkdir(parents=True, exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = folder / f"crash-{stamp}-{os.getpid()}.log"
        details = "".join(traceback.format_exception(kind, value, tb))
        frozen = getattr(sys, "frozen", False)
        header = (
            f"BrunelleschiBIM {__version__}, Python {sys.version.split()[0]}, frozen={frozen}\n"
        )
        path.write_text(header + details, encoding="utf-8")
        return path
    except OSError:
        return None


def message(value: BaseException, log: Path | None) -> str:
    where = f"Details were written to:\n{log}" if log else "The details could not be saved."
    return f"BrunelleschiBIM met an unexpected error:\n\n{type(value).__name__}: {value}\n\n{where}"


def install(show: bool = True) -> None:
    """Route unexpected errors (also those raised inside Qt slots, which PySide6 passes to
    ``sys.excepthook``) to a log file and, if ``show``, a message box."""

    def hook(kind: type[BaseException], value: BaseException, tb: TracebackType | None) -> None:
        log = write_crash_log(kind, value, tb)
        if sys.stderr is not None:
            traceback.print_exception(kind, value, tb)
        if show:
            show_message(message(value, log))

    sys.excepthook = hook


def show_message(text: str) -> None:
    """A message box, with Qt if an application exists, else with Windows itself."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is not None:
            QMessageBox.critical(None, "BrunelleschiBIM", text)
            return
    except Exception:  # Qt itself may be what failed
        pass
    if os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, "BrunelleschiBIM", 0x10)
