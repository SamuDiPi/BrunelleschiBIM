"""Render the 3D view of a project to a PNG, without opening any window.

    uv run python tools/render_3d.py PROJECT.bbim OUT.png [--select KIND:INDEX]
                                     [--yaw DEG] [--pitch DEG] [--size 1200x800]

It uses Qt's normal platform with an off-screen OpenGL surface: nothing appears on the
screen. (Qt's "offscreen" platform, used by the tests, has no OpenGL on Windows.)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the 3D view of a project to a PNG.")
    parser.add_argument("project")
    parser.add_argument("output")
    parser.add_argument("--select", help="for example door:0")
    parser.add_argument("--yaw", type=float, default=-45.0)
    parser.add_argument("--pitch", type=float, default=30.0)
    parser.add_argument("--size", default="1200x800")
    args = parser.parse_args()

    from PySide6.QtGui import QGuiApplication

    from brunelleschi import api
    from brunelleschi.gui.camera import OrbitCamera
    from brunelleschi.gui.renderer import render_offscreen
    from brunelleschi.gui.scene3d import build_scene

    _app = QGuiApplication(sys.argv[:1])
    project = api.load(Path(args.project))
    scene = build_scene(project)
    bounds = scene.bounds()
    if bounds is None:
        print("the project has nothing to draw in 3D", file=sys.stderr)
        return 1
    camera = OrbitCamera.default()
    camera.yaw, camera.pitch = args.yaw, args.pitch
    camera.fit(*bounds)
    selected = -1
    if args.select:
        kind, number = args.select.split(":")
        stores = {"wall": project.walls, "door": project.doors, "window": project.windows}
        selected = scene.index_of(stores[kind][int(number)].id)
    width, height = (int(v) for v in args.size.split("x"))
    image = render_offscreen(scene, camera.matrix(width, height), width, height, selected)
    if image is None:
        print("OpenGL 3.3 is not available", file=sys.stderr)
        return 1
    image.save(args.output)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
