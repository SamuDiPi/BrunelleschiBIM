"""Triangle meshes of walls, doors and windows, for display.

A wall is the prism of its joined footprint (mitres and tees included) between its base
and top, with its openings cut out. Openings always cross the whole thickness, so the
solid is built without general booleans: the footprint is cut across the wall at the
start and end of every opening, and each slice is extruded over the heights not taken by
an opening. Faces between neighbouring slices lie inside the solid and are never seen;
the faces of the slices next to an opening are its jambs, head and sill.

Everything is in model metres. Triangles are counter-clockwise seen from outside.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray
from shapely import Polygon, box, delaunay_triangles
from shapely.geometry.polygon import orient

from brunelleschi.geometry.joins import Vec, WallLine


@dataclass(frozen=True, slots=True)
class Mesh:
    vertices: NDArray[np.float64]  # (n, 3)
    triangles: NDArray[np.int32]  # (m, 3), indices into vertices

    @staticmethod
    def empty() -> Mesh:
        return Mesh(np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int32))

    def volume(self) -> float:
        """Signed volume (divergence theorem); internal faces cancel out."""
        if len(self.triangles) == 0:
            return 0.0
        a, b, c = (self.vertices[self.triangles[:, k]] for k in range(3))
        return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)

    def bounds(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        return self.vertices.min(axis=0), self.vertices.max(axis=0)


def merge(meshes: Sequence[Mesh]) -> Mesh:
    vertices, triangles, offset = [], [], 0
    for m in meshes:
        vertices.append(m.vertices)
        triangles.append(m.triangles + offset)
        offset += len(m.vertices)
    if not vertices:
        return Mesh.empty()
    return Mesh(np.vstack(vertices), np.vstack(triangles).astype(np.int32))


def prism(outline: Sequence[Vec], z0: float, z1: float) -> Mesh:
    """A convex or concave simple polygon extruded from z0 to z1 (z1 > z0)."""
    poly = orient(Polygon(outline), 1.0)  # counter-clockwise
    ring = _coords(poly)
    n = len(ring)
    vertices = np.array([(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring], float)
    tris: list[tuple[int, int, int]] = []
    # Caps: fan triangulation is enough for the convex slices built below; concave
    # outlines go through shapely's triangulation.
    if poly.convex_hull.area - poly.area < 1e-12:
        cap = [(0, i, i + 1) for i in range(1, n - 1)]
    else:
        cap = _triangulate(poly, ring)
    for i, j, k in cap:
        tris.append((i, k, j))  # bottom, facing down
        tris.append((n + i, n + j, n + k))  # top, facing up
    for i in range(n):
        j = (i + 1) % n
        tris.append((i, j, n + j))
        tris.append((i, n + j, n + i))
    return Mesh(vertices, np.array(tris, dtype=np.int32))


def _coords(poly: Polygon) -> list[Vec]:
    """The exterior ring's points, without the closing repeat."""
    return [(float(x), float(y)) for x, y in list(poly.exterior.coords)[:-1]]


def _triangulate(poly: Polygon, ring: list[Vec]) -> list[tuple[int, int, int]]:
    """Triangles of a concave polygon, as indices into ``ring``."""
    index = {(round(x, 9), round(y, 9)): i for i, (x, y) in enumerate(ring)}
    result: list[tuple[int, int, int]] = []
    for tri in delaunay_triangles(poly).geoms:
        if not isinstance(tri, Polygon) or not poly.contains(tri.centroid):
            continue
        a, b, c = (index[(round(x, 9), round(y, 9))] for x, y in _coords(orient(tri, 1.0)))
        result.append((a, b, c))
    return result


def wall_mesh(
    line: WallLine,
    footprint: Sequence[Vec],
    openings: Sequence[tuple[float, float, float, float]],
) -> Mesh:
    """The wall solid. ``openings`` are (along start, along end, bottom z, top z) with
    absolute elevations; along distances are from the wall's start on its centre line."""
    (sx, sy), (dx, dy) = line.start, line.direction

    def to_local(p: Vec) -> Vec:
        rx, ry = p[0] - sx, p[1] - sy
        return (rx * dx + ry * dy, dx * ry - dy * rx)

    def to_world(p: Vec) -> Vec:
        u, v = p
        return (sx + dx * u - dy * v, sy + dy * u + dx * v)

    local = Polygon([to_local(p) for p in footprint])
    cuts = sorted({a for a, _, _, _ in openings} | {b for _, b, _, _ in openings})
    u_min, _, u_max, _ = local.bounds
    edges = [u_min, *[u for u in cuts if u_min < u < u_max], u_max]
    pieces: list[Mesh] = []
    margin = line.thickness + 1.0  # wider than the wall, for the clipping boxes
    for u0, u1 in pairwise(edges):
        if u1 - u0 < 1e-9:
            continue
        piece = local.intersection(box(u0, -margin, u1, margin))
        if piece.is_empty or piece.area < 1e-12 or not isinstance(piece, Polygon):
            continue
        middle = (u0 + u1) / 2
        holes = sorted((z0, z1) for a, b, z0, z1 in openings if a <= middle <= b)
        outline = [to_world(p) for p in _coords(piece)]
        z = line.base_z
        for h0, h1 in holes:
            if h0 - z > 1e-9:
                pieces.append(prism(outline, z, min(h0, line.top_z)))
            z = max(z, h1)
        if line.top_z - z > 1e-9:
            pieces.append(prism(outline, z, line.top_z))
    return merge(pieces)
