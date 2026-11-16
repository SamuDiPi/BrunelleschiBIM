"""Entry point of the packaged BrunelleschiBIM.exe (see ADR 0009 and tools/build_exe.py).

    BrunelleschiBIM.exe [PROJECT.bbim]          the application
    BrunelleschiBIM.exe --selftest OUT_DIR      checks, no window (see brunelleschi.gui.selftest)
    BrunelleschiBIM.exe --selftest-gl OUT_DIR   the 3D drawing, off screen

Anything else on the command line is refused before a window exists, because libraries
may relaunch ``sys.executable`` (that is this program) with their own arguments.
"""

from __future__ import annotations

import sys


def _main() -> int:
    args = sys.argv[1:]
    if len(args) == 2 and args[0] in ("--selftest", "--selftest-gl"):
        from brunelleschi.gui import crash, selftest

        crash.install(show=False)  # a self-test never shows anything
        return selftest.run(args[1], gl=args[0] == "--selftest-gl")
    from brunelleschi.gui import crash

    crash.install(show=True)
    from brunelleschi.gui.app import main

    return main(args)


if __name__ == "__main__":
    try:
        code = _main()
    except SystemExit:
        raise
    except BaseException:  # start-up errors: log and say so, never PyInstaller's dialog
        from brunelleschi.gui import crash

        kind, value, tb = sys.exc_info()
        assert kind is not None and value is not None
        log = crash.write_crash_log(kind, value, tb)
        if not (len(sys.argv) > 1 and sys.argv[1].startswith("--selftest")):
            crash.show_message(crash.message(value, log))
        code = 3
    sys.exit(code)
