"""The 3D scene: every element's mesh in one flat array, ready for OpenGL and for picking.

Each triangle vertex carries position, flat normal, colour and the index of its element,
so the whole model is drawn with one call and the selected element is highlighted by
index in the shader.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import numpy as np
from numpy.typing import NDArray

from brunelleschi import api
from brunelleschi.geometry.solids import Mesh
from brunelleschi.gui.camera import ray_hit
from brunelleschi.regen.meshes import element_meshes

COLOURS: dict[str, tuple[float, float, float]] = {
    "wall": (0.86, 0.84, 0.79),
    "door": (0.55, 0.36, 0.21),
    "window": (0.45, 0.65, 0.90),
    "reference": (0.78, 0.78, 0.80),
}
FLOATS_PER_VERTEX = 10  # position 3, normal 3, colour 3, element index 1


@dataclass
class Scene:
    data: NDArray[np.float32] = field(
        default_factory=lambda: np.zeros((0, FLOATS_PER_VERTEX), np.float32)
    )
    vertices: NDArray[np.float64] = field(default_factory=lambda: np.zeros((0, 3)))
    triangles: NDArray[np.int32] = field(default_factory=lambda: np.zeros((0, 3), np.int32))
    triangle_element: NDArray[np.int32] = field(default_factory=lambda: np.zeros(0, np.int32))
    elements: list[UUID | str] = field(default_factory=list)  # str: a reference element

    @property
    def empty(self) -> bool:
        return len(self.triangles) == 0

    def bounds(self) -> tuple[NDArray[np.float64], NDArray[np.float64]] | None:
        if self.empty:
            return None
        return self.vertices.min(axis=0), self.vertices.max(axis=0)

    def index_of(self, element_id: UUID | None) -> int:
        """Shader index of an element, or -1."""
        try:
            return self.elements.index(element_id) if element_id is not None else -1
        except ValueError:
            return -1

    def pick(
        self, origin: NDArray[np.float64], direction: NDArray[np.float64]
    ) -> UUID | str | None:
        hit = ray_hit(origin, direction, self.vertices, self.triangles)
        if hit is None:
            return None
        return self.elements[int(self.triangle_element[hit[0]])]


def build_scene(project: api.Project, references: Sequence[tuple[str, Any]] = ()) -> Scene:
    """The model's elements, then the elements of loaded references, as (reference name,
    ReferenceModel) pairs; reference elements are labelled, not selectable."""
    parts: list[tuple[UUID | str, str, Mesh]] = [
        (element_id, em.kind, em.mesh) for element_id, em in element_meshes(project).items()
    ]
    for name, model in references:
        for e in model.elements:
            label = f"{name}: {e.ifc_class} {e.name!r}".rstrip()
            parts.append((label, "reference", Mesh(e.vertices, e.triangles)))
    chunks: list[NDArray[np.float32]] = []
    vertices: list[NDArray[np.float64]] = []
    triangles: list[NDArray[np.int32]] = []
    owner: list[NDArray[np.int32]] = []
    elements: list[UUID | str] = []
    offset = 0
    for index, (element_id, kind, mesh) in enumerate(parts):
        elements.append(element_id)
        if len(mesh.triangles) == 0:
            continue
        tri = mesh.vertices[mesh.triangles]  # (m, 3, 3)
        normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-12
        n = len(tri) * 3
        data = np.empty((n, FLOATS_PER_VERTEX), np.float32)
        data[:, 0:3] = tri.reshape(-1, 3)
        data[:, 3:6] = np.repeat(normals, 3, axis=0)
        data[:, 6:9] = COLOURS.get(kind, (0.7, 0.7, 0.7))
        data[:, 9] = index
        chunks.append(data)
        vertices.append(mesh.vertices)
        triangles.append(mesh.triangles + offset)
        owner.append(np.full(len(mesh.triangles), index, np.int32))
        offset += len(mesh.vertices)
    if not chunks:
        return Scene(elements=elements)
    return Scene(
        data=np.concatenate(chunks),
        vertices=np.vstack(vertices),
        triangles=np.vstack(triangles).astype(np.int32),
        triangle_element=np.concatenate(owner),
        elements=elements,
    )
