"""Probe A, fair version: one merged PolyData for the scene, element index as cell data."""
import sys, time
import numpy as np
import pyvista as pv
import vtk
from meshes import grid, house, triangulate
W, H = 1280, 800

def run(name, project):
    meshes, stats = triangulate(project)
    t = time.perf_counter()
    verts, faces, ids, cols, off = [], [], [], [], 0
    for i, m in enumerate(meshes):
        verts.append(m.vertices); faces.append(np.hstack([np.full((len(m.faces), 1), 3), m.faces + off]))
        ids.append(np.full(len(m.faces), i)); cols.append(np.tile(np.array(m.colour) * 255, (len(m.faces), 1)))
        off += len(m.vertices)
    poly = pv.PolyData(np.vstack(verts), np.vstack(faces).ravel())
    poly.cell_data["element"] = np.concatenate(ids)
    poly.cell_data["rgb"] = np.vstack(cols).astype(np.uint8)
    pl = pv.Plotter(off_screen=True, window_size=(W, H)); pl.set_background("white")
    pl.add_mesh(poly, scalars="rgb", rgb=True, smooth_shading=False)
    pl.view_isometric(); build = time.perf_counter() - t
    t = time.perf_counter(); pl.show(auto_close=False); first = time.perf_counter() - t
    t = time.perf_counter()
    for _ in range(60):
        pl.camera.azimuth += 2; pl.render()
    per = (time.perf_counter() - t) / 60
    pl.camera.azimuth = 0; pl.view_isometric(); pl.render()
    target = next(i for i, m in enumerate(meshes) if m.kind == "IfcWall")
    r = pl.renderer; r.SetWorldPoint(*meshes[target].vertices.mean(axis=0), 1.0); r.WorldToDisplay()
    x, y, _ = r.GetDisplayPoint()
    picker = vtk.vtkCellPicker(); res = []
    for _ in range(2):
        t = time.perf_counter(); picker.Pick(int(x), int(y), 0, r); res.append(time.perf_counter() - t)
    cell = picker.GetCellId()
    hit = poly.cell_data["element"][cell] if cell >= 0 else -1
    print(f"{name} merged: scene {build:.3f}s, first frame {first:.3f}s, {per*1000:.1f} ms/frame, "
          f"pick {res[0]*1000:.1f} ms (again {res[1]*1000:.1f} ms) -> {'the right wall' if hit == target else hit}")
    pl.close()

run("house", house()); run("grid 15", grid(15))
info = vtk.vtkRenderWindow(); info.SetOffScreenRendering(1); info.Render()
print("VTK OpenGL:", info.ReportCapabilities().splitlines()[0:3])
