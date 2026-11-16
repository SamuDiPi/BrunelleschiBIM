"""Probe C: pygfx on wgpu, rendered off screen (no window)."""

import sys
import time

import numpy as np
import pygfx as gfx
from PIL import Image
from rendercanvas.offscreen import RenderCanvas

from meshes import grid, house, triangulate

W, H = 1280, 800


def scene(meshes):
    t = time.perf_counter()
    canvas = RenderCanvas(size=(W, H), pixel_ratio=1)
    renderer = gfx.renderers.WgpuRenderer(canvas)
    sc = gfx.Scene()
    sc.add(gfx.Background.from_color("#ffffff"))
    sc.add(gfx.AmbientLight(intensity=0.6))
    light = gfx.DirectionalLight(intensity=2.0)
    light.local.position = (1, 2, 3)
    sc.add(light)
    objects = {}
    for m in meshes:
        geometry = gfx.Geometry(positions=m.vertices, indices=m.faces)
        material = gfx.MeshPhongMaterial(color=m.colour, flat_shading=True, pick_write=True)
        obj = gfx.Mesh(geometry, material)
        sc.add(obj)
        objects[m.name] = obj
    camera = gfx.PerspectiveCamera(30, W / H)
    camera.show_object(sc, view_dir=(-1, 1, -0.8), up=(0, 0, 1))
    canvas.request_draw(lambda: renderer.render(sc, camera))
    return canvas, renderer, sc, camera, objects, time.perf_counter() - t


def to_screen(camera, point):
    p = np.array([*point, 1.0])
    clip = camera.camera_matrix @ p
    ndc = clip[:3] / clip[3]
    return int((ndc[0] + 1) / 2 * W), int((1 - ndc[1]) / 2 * H)


def run(name, project, out):
    meshes, stats = triangulate(project)
    canvas, renderer, sc, camera, objects, build = scene(meshes)
    t = time.perf_counter()
    image = np.asarray(canvas.draw())
    first = time.perf_counter() - t
    frames = 60
    t = time.perf_counter()
    for _ in range(frames):
        camera.local.position = camera.local.position  # a camera change forces a redraw
        canvas.draw()
    per_frame = (time.perf_counter() - t) / frames
    target = next(m for m in meshes if m.kind == "IfcWall")
    x, y = to_screen(camera, target.vertices.mean(axis=0))
    t = time.perf_counter()
    info = renderer.get_pick_info((x, y))
    pick_s = time.perf_counter() - t
    t = time.perf_counter()
    info = renderer.get_pick_info((x, y))
    pick2_s = time.perf_counter() - t
    hit_obj = info.get("world_object")
    hit = next((k for k, o in objects.items() if o is hit_obj), None)
    hit = ("the right wall" if hit == target.name else f"another element {hit}") if hit else "nothing"
    Image.fromarray(image[:, :, :3]).save(out)
    print(
        f"{name}: {len(meshes)} meshes, {stats['triangles']} triangles; scene {build:.3f}s, "
        f"first frame {first:.3f}s, {per_frame * 1000:.1f} ms/frame, pick {pick_s * 1000:.1f} ms "
        f"(again {pick2_s * 1000:.1f} ms) -> {hit}"
    )


if __name__ == "__main__":
    out = sys.argv[1]
    run("house", house(), f"{out}/pygfx-house.png")
    run("grid 15", grid(15), f"{out}/pygfx-grid.png")
