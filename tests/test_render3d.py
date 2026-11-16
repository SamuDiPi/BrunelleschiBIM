"""The 3D drawing itself, in a separate process on Qt's normal platform.

The test suite runs Qt on the "offscreen" platform, which has no OpenGL on Windows. This
test starts a child process that draws into an off-screen surface (no window is ever
created on the screen) and checks pixels. It is skipped, with the reason, where OpenGL
3.3 is not available (CI runners, software-only drivers, no display server).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = r"""
import json, sys
from PySide6.QtGui import QGuiApplication
from brunelleschi import api
from brunelleschi.gui.camera import OrbitCamera
from brunelleschi.gui.renderer import BACKGROUND, render_offscreen
from brunelleschi.gui.scene3d import build_scene

app = QGuiApplication([])
p = api.new_project("P")
g = api.add_level(p, "G", 0.0); f = api.add_level(p, "F", 3.0)
c = [(0, 0), (6, 0), (6, 4), (0, 4)]
w = [api.add_wall(p, s, c[(i + 1) % 4], 0.3, g.id, top_level=f.id) for i, s in enumerate(c)]
door = api.add_door(p, w[0].id, 1.5, 0.9, 2.1)
scene = build_scene(p)
cam = OrbitCamera.default(); cam.fit(*scene.bounds())
W, H = 400, 300
plain = render_offscreen(scene, cam.matrix(W, H), W, H)
if plain is None:
    print(json.dumps({"unavailable": True})); sys.exit(0)
selected = render_offscreen(scene, cam.matrix(W, H), W, H, selected=scene.index_of(door.id))
plain.save(sys.argv[1] + "/plain.png"); selected.save(sys.argv[1] + "/selected.png")
bg = tuple(round(v * 255) for v in BACKGROUND[:3])
def colours(img):
    out = []
    for y in range(0, H, 3):
        for x in range(0, W, 3):
            c = img.pixelColor(x, y); out.append((c.red(), c.green(), c.blue()))
    return out
a, b = colours(plain), colours(selected)
print(json.dumps({
    "corner": list(a[0]), "background": list(bg),
    "model_pixels": sum(1 for c in a if max(abs(c[i] - bg[i]) for i in range(3)) > 8),
    "changed_by_selection": sum(1 for x, y in zip(a, b) if x != y),
    "bluish_when_selected": sum(1 for c in b if c[2] > c[0] + 40),
    "bluish_plain": sum(1 for c in a if c[2] > c[0] + 40),
}))
"""


def test_house_is_drawn_and_selection_highlighted(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}  # normal platform
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(tmp_path)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = result.stdout.strip().splitlines()
    if result.returncode != 0:
        if "platform plugin" in result.stderr or "display" in result.stderr.lower():
            pytest.skip("no Qt platform with a display here")
        pytest.fail(result.stderr[-2000:])
    data = json.loads(output[-1])
    if data.get("unavailable"):
        pytest.skip("OpenGL 3.3 is not available here")
    assert data["corner"] == data["background"]
    assert data["model_pixels"] > 1000  # the house covers a good part of the image
    assert data["changed_by_selection"] > 50  # the door is highlighted ...
    assert data["bluish_when_selected"] > data["bluish_plain"]  # ... in blue
