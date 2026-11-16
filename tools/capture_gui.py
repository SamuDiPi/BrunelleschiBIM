"""Capture the main window as a PNG, without showing anything on the screen.

    uv run python tools/capture_gui.py PROJECT.bbim OUT.png [--select KIND:INDEX] [--level NAME]

KIND is level, wall, door or window and INDEX its position in creation order (from 0).
Qt runs on its "offscreen" platform, which draws into memory only.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

WINDOWS_FONTS = Path(r"C:\Windows\Fonts")


def prepare_qt_environment() -> None:
    """Must run before Qt is imported."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"  # never touch the screen
    # The offscreen platform has no font database of its own; without this, text is boxes.
    if os.name == "nt" and WINDOWS_FONTS.is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", str(WINDOWS_FONTS))


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture the main window as a PNG.")
    parser.add_argument("project")
    parser.add_argument("output")
    parser.add_argument("--select", help="for example wall:0")
    parser.add_argument("--level", help="level shown in the plan (start of its name)")
    parser.add_argument("--size", default="1280x800")
    args = parser.parse_args()

    prepare_qt_environment()
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from brunelleschi.gui.document import Document
    from brunelleschi.gui.main_window import MainWindow

    app = QApplication(sys.argv[:1])
    # The default UI font on Windows 11 (Segoe UI) is a variable font, which the offscreen
    # platform's font engine draws with wrong glyphs; a plain font gives a faithful capture.
    app.setFont(QFont("Arial", 9))
    window = MainWindow(Document())
    width, height = (int(v) for v in args.size.split("x"))
    window.resize(width, height)
    if not window.open_file(Path(args.project)):
        print(window.status.text(), file=sys.stderr)
        return 1
    project = window.document.project
    if args.level:
        for i in range(window.level_combo.count()):
            if window.level_combo.itemText(i).startswith(args.level):
                window.level_combo.setCurrentIndex(i)
    if args.select:
        kind, number = args.select.split(":")
        stores = {
            "level": project.levels,
            "wall": project.walls,
            "door": project.doors,
            "window": project.windows,
        }
        window.document.select(stores[kind][int(number)].id)
    window.show()  # on the offscreen platform this only lays the window out in memory
    app.processEvents()
    window.plan.fit()
    app.processEvents()
    window.grab().save(args.output)
    print(f"wrote {args.output} ({app.platformName()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
