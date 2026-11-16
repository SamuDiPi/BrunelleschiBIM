"""Packaging probe: the whole stack in one program.

    pkg_app --selftest OUT_DIR   build the M7 house, export IFC (validated) and SVG, create
                                 an OpenGL context, write a report; shows no window
    pkg_app                      a minimal main window (not used by the probe)
"""

import sys
import time

T0 = time.perf_counter()


def selftest(out: str) -> int:
    from pathlib import Path

    from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat

    from brunelleschi import __version__, api
    from brunelleschi.ifc import validate_ifc, write_ifc

    t_import = time.perf_counter() - T0
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    p = api.new_project("Casa")
    g = api.add_level(p, "Piano terra", 0.0)
    f = api.add_level(p, "Primo piano", 3.0)
    c = [(0, 0), (6, 0), (6, 4), (0, 4)]
    w = [api.add_wall(p, s, c[(i + 1) % 4], 0.3, g.id, top_level=f.id) for i, s in enumerate(c)]
    api.add_door(p, w[0].id, 1.5, 0.9, 2.1)
    api.add_window(p, w[2].id, 3.0, 1.2, 1.4, 0.9)
    api.save(p, folder / "casa.bbim")
    write_ifc(p, folder / "casa.ifc")
    result = validate_ifc(folder / "casa.ifc")
    api.write_plan_svg(p, "Piano terra", folder / "casa.svg", api.Sheet("A4"))

    app = QGuiApplication(sys.argv[:1])
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    ctx = QOpenGLContext()
    ctx.setFormat(fmt)
    gl_ok = ctx.create()
    surface = QOffscreenSurface()
    surface.setFormat(ctx.format())
    surface.create()
    gl = "none"
    if gl_ok and ctx.makeCurrent(surface):
        from OpenGL import GL

        gl = f"{GL.glGetString(GL.GL_VERSION).decode()} / {GL.glGetString(GL.GL_RENDERER).decode()}"
    report = (
        f"bbim {__version__}; python {sys.version.split()[0]}; frozen={getattr(sys, 'frozen', False)}\n"
        f"imports {t_import:.2f}s, total {time.perf_counter() - T0:.2f}s\n"
        f"ifc issues {len(result.issues)} (rules checked: {result.rules_checked})\n"
        f"opengl {gl}\n"
    )
    (folder / "report.txt").write_text(report, encoding="utf-8")
    del app
    return 0


def window() -> int:
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setCentralWidget(QLabel("BrunelleschiBIM packaging probe"))
    win.show()
    return app.exec()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--selftest":
        sys.exit(selftest(sys.argv[2]))
    if len(sys.argv) > 1:
        # A library that runs `sys.executable something.py` relaunches this program in a
        # frozen build. Never open a window for an invocation we do not recognise.
        print(f"pkg_app: unexpected arguments {sys.argv[1:]}", file=sys.stderr)
        sys.exit(2)
    sys.exit(window())
