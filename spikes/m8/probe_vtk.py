"""Probe A: PyVista/VTK, rendered off screen (no window)."""

import sys
import time

import numpy as np
import pyvista as pv

from meshes import grid, house, triangulate

W, H = 1280, 800


def scene(meshes):
    t = time.perf_counter()
    pl = pv.Plotter(off_screen=True, window_size=(W, H))
    pl.set_background("white")
    actors = {}
    for m in meshes:
        faces = np.hstack([np.full((len(m.faces), 1), 3), m.faces]).ravel()
        poly = pv.PolyData(m.vertices, faces)
        actor = pl.add_mesh(poly, color=m.colour, show_edges=False, smooth_shading=False)
        actors[m.name] = actor
    pl.view_isometric()
    pl.camera.zoom(1.2)
    return pl, actors, time.perf_counter() - t


def run(name, project, out):
    meshes, stats = triangulate(project)
    pl, actors, build = scene(meshes)
    t = time.perf_counter()
    pl.show(auto_close=False)  # first frame
    first = time.perf_counter() - t
    frames = 60
    t = time.perf_counter()
    for _ in range(frames):
        pl.camera.azimuth += 2
        pl.render()
    per_frame = (time.perf_counter() - t) / frames
    # Picking: project the centre of the first wall's outer face to the screen, pick there.
    import vtk

    pl.camera.azimuth = 0
    pl.view_isometric()
    pl.camera.zoom(1.2)
    pl.render()
    target = next(m for m in meshes if m.kind == "IfcWall")
    centre = target.vertices.mean(axis=0)
    r = pl.renderer
    r.SetWorldPoint(*centre, 1.0)
    r.WorldToDisplay()
    x, y, _ = r.GetDisplayPoint()
    picker = vtk.vtkPropPicker()
    t = time.perf_counter()
    picked = picker.PickProp(int(x), int(y), r)
    pick_s = time.perf_counter() - t
    t = time.perf_counter()
    picker.PickProp(int(x), int(y), r)
    pick2_s = time.perf_counter() - t
    prop = picker.GetViewProp()
    hit = next((k for k, a in actors.items() if a is prop), None)
    hit = ("the right wall" if hit == target.name else f"another element {hit}") if hit else None
    pl.screenshot(out)
    print(
        f"{name}: {len(meshes)} meshes, {stats['triangles']} triangles; "
        f"scene {build:.3f}s, first frame {first:.3f}s, {per_frame * 1000:.1f} ms/frame, "
        f"pick {pick_s * 1000:.1f} ms (again {pick2_s * 1000:.1f} ms) -> {'hit ' + hit if hit else 'nothing'} ({picked})"
    )
    pl.close()


if __name__ == "__main__":
    out = sys.argv[1]
    run("house", house(), f"{out}/vtk-house.png")
    run("grid 15", grid(15), f"{out}/vtk-grid.png")
