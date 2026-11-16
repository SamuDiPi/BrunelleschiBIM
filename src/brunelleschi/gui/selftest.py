"""A self-test the packaged program can run on any machine, without showing anything.

    BrunelleschiBIM.exe --selftest OUT_DIR      everything but OpenGL, on Qt's offscreen platform
    BrunelleschiBIM.exe --selftest-gl OUT_DIR   the 3D view drawn on an off-screen surface

Each writes ``report.json`` and its files into OUT_DIR and exits 0 when every check passed.
It exercises the parts most likely to break in a frozen build: IfcOpenShell (export,
validation, reading back with its geometry iterator), ezdxf, Shapely, pydantic, Qt.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from brunelleschi import __version__, api


def _house() -> api.Project:
    p = api.new_project("Self-test")
    g = api.add_level(p, "Ground", 0.0)
    f = api.add_level(p, "First", 3.0)
    c = [(0, 0), (6, 0), (6, 4), (0, 4)]
    w = [api.add_wall(p, s, c[(i + 1) % 4], 0.3, g.id, top_level=f.id) for i, s in enumerate(c)]
    api.add_door(p, w[0].id, 1.5, 0.9, 2.1)
    api.add_window(p, w[2].id, 3.0, 1.2, 1.4, 0.9)
    return p


def _checks(out: Path, gl: bool) -> list[tuple[str, Callable[[], object]]]:
    project = _house()

    def save() -> object:
        api.save(project, out / "house.bbim")
        return api.load(out / "house.bbim") == project

    def ifc() -> object:
        from brunelleschi.ifc import validate_ifc, write_ifc

        write_ifc(project, out / "house.ifc")
        result = validate_ifc(out / "house.ifc")
        return {"issues": len(result.issues), "rules": result.rules_checked}

    def reference() -> object:
        from brunelleschi.ifc.reference import load_reference

        model = load_reference(out / "house.ifc")
        assert len(model.elements) == 6, model.summary()
        return model.summary()

    def svg() -> object:
        api.write_plan_svg(project, "Ground", out / "plan.svg", api.Sheet("A4", scale=50))
        return (out / "plan.svg").stat().st_size

    def dxf() -> object:
        api.write_plan_dxf(project, "Ground", out / "plan.dxf")
        return (out / "plan.dxf").stat().st_size

    def window() -> object:
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication

        from brunelleschi.gui.document import Document
        from brunelleschi.gui.main_window import MainWindow

        app = QApplication.instance() or QApplication(sys.argv[:1])
        assert isinstance(app, QApplication)
        app.setFont(QFont("Arial", 9))
        win = MainWindow(Document())
        win.resize(1280, 800)
        assert win.open_file(out / "house.bbim")
        win.show()  # offscreen platform: in memory only
        app.processEvents()
        assert win.grab().save(str(out / "window.png"))
        return app.platformName()

    def render_3d() -> object:
        from PySide6.QtGui import QGuiApplication

        from brunelleschi.gui.camera import OrbitCamera
        from brunelleschi.gui.renderer import render_offscreen
        from brunelleschi.gui.scene3d import build_scene

        _app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
        scene = build_scene(project)
        bounds = scene.bounds()
        assert bounds is not None
        camera = OrbitCamera.default()
        camera.fit(*bounds)
        image = render_offscreen(scene, camera.matrix(800, 600), 800, 600)
        if image is None:
            return "OpenGL 3.3 not available"
        assert image.save(str(out / "3d.png"))
        return "drawn"

    if gl:
        return [("3d", render_3d)]
    return [
        ("save", save),
        ("ifc", ifc),
        ("reference", reference),
        ("svg", svg),
        ("dxf", dxf),
        ("window", window),
    ]


def run(out_dir: str, gl: bool = False) -> int:
    """Run the checks, write ``report.json``, return the exit code (0: all passed)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if not gl:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"  # never a window on the screen
        fonts = Path(r"C:\Windows\Fonts")
        if os.name == "nt" and fonts.is_dir():
            os.environ.setdefault("QT_QPA_FONTDIR", str(fonts))
    report: dict[str, Any] = {
        "version": __version__,
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version.split()[0],
        "checks": {},
    }
    ok = True
    start = time.perf_counter()
    for name, check in _checks(out, gl):
        t = time.perf_counter()
        try:
            result: object = check()
            passed = result is not False
        except Exception as exc:
            result, passed = f"{type(exc).__name__}: {exc}", False
            report.setdefault("tracebacks", {})[name] = traceback.format_exc()
        ok = ok and passed
        report["checks"][name] = {
            "passed": passed,
            "result": result,
            "seconds": round(time.perf_counter() - t, 3),
        }
    report["seconds"] = round(time.perf_counter() - start, 3)
    report["passed"] = ok
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("--selftest", "--selftest-gl"):
        sys.exit(__doc__)
    sys.exit(run(sys.argv[2], gl=sys.argv[1] == "--selftest-gl"))
