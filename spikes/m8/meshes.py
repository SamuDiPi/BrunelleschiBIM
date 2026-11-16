"""Shared by the 3D probes: build test models and triangulate them with IfcOpenShell."""

from __future__ import annotations

import time
from dataclasses import dataclass

import ifcopenshell.geom
import numpy as np

from brunelleschi import api
from brunelleschi.ifc import export_ifc


@dataclass
class Mesh:
    name: str
    kind: str
    vertices: np.ndarray  # (n, 3) float32
    faces: np.ndarray  # (m, 3) int32
    colour: tuple[float, float, float]


COLOURS = {
    "IfcWall": (0.85, 0.83, 0.78),
    "IfcDoor": (0.55, 0.35, 0.20),
    "IfcWindow": (0.45, 0.65, 0.90),
}


def house() -> api.Project:
    p = api.new_project("Casa")
    g = api.add_level(p, "Piano terra", 0.0)
    f = api.add_level(p, "Primo piano", 3.0)
    c = [(0, 0), (6, 0), (6, 4), (0, 4)]
    w = [api.add_wall(p, s, c[(i + 1) % 4], 0.3, g.id, top_level=f.id) for i, s in enumerate(c)]
    api.add_door(p, w[0].id, 1.5, 0.9, 2.1)
    api.add_window(p, w[2].id, 3.0, 1.2, 1.4, 0.9)
    return p


def grid(n: int) -> api.Project:
    """n x n rooms of 5 x 4 m, every wall a separate piece, a door in each vertical piece."""
    p = api.new_project(f"Grid {n}")
    g = api.add_level(p, "G", 0.0)
    f = api.add_level(p, "F", 3.0)
    with api.transaction(p):
        for i in range(n + 1):
            for k in range(n):
                api.add_wall(p, (5 * k, 4 * i), (5 * (k + 1), 4 * i), 0.3, g.id, top_level=f.id)
                w = api.add_wall(p, (5 * i, 4 * k), (5 * i, 4 * (k + 1)), 0.3, g.id, top_level=f.id)
                api.add_door(p, w.id, 2.0, 0.9, 2.1)
    return p


def triangulate(project: api.Project) -> tuple[list[Mesh], dict[str, float]]:
    t0 = time.perf_counter()
    f = export_ifc(project)
    t1 = time.perf_counter()
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    meshes = []
    iterator = ifcopenshell.geom.iterator(settings, f, include=f.by_type("IfcElement"))
    iterator.initialize()
    while True:
        shape = iterator.get()
        element = f.by_id(shape.id)
        kind = element.is_a()
        if kind in COLOURS:
            v = np.array(shape.geometry.verts, dtype=np.float32).reshape(-1, 3)
            fc = np.array(shape.geometry.faces, dtype=np.int32).reshape(-1, 3)
            meshes.append(Mesh(element.GlobalId, kind, v, fc, COLOURS[kind]))
        if not iterator.next():
            break
    t2 = time.perf_counter()
    triangles = sum(len(m.faces) for m in meshes)
    return meshes, {"export_s": t1 - t0, "triangulate_s": t2 - t1, "triangles": triangles}


if __name__ == "__main__":
    for name, model in (("house", house()), ("grid 15", grid(15))):
        meshes, stats = triangulate(model)
        print(name, len(model.walls), "walls", len(meshes), "meshes", stats)
