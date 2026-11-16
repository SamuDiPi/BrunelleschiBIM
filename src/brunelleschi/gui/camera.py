"""Orbit camera and ray picking for the 3D view: plain numpy, no OpenGL, testable.

The camera looks at ``target`` from ``distance`` metres, turned ``yaw`` degrees around the
vertical axis and raised ``pitch`` degrees above the horizon. Z is up, as in the model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

F = NDArray[np.float64]


@dataclass
class OrbitCamera:
    target: F
    distance: float = 20.0
    yaw: float = -45.0  # degrees; -45 looks from the south-west towards the north-east
    pitch: float = 30.0  # degrees above the horizon
    fov: float = 40.0  # vertical field of view, degrees

    @staticmethod
    def default() -> OrbitCamera:
        return OrbitCamera(target=np.zeros(3))

    def eye(self) -> F:
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        direction = np.array([math.cos(p) * math.sin(y), -math.cos(p) * math.cos(y), math.sin(p)])
        return np.asarray(self.target + direction * self.distance, dtype=np.float64)

    def view(self) -> F:
        eye, target = self.eye(), self.target
        f = target - eye
        f /= np.linalg.norm(f)
        up = np.array([0.0, 0.0, 1.0])
        s = np.cross(f, up)
        if np.linalg.norm(s) < 1e-9:  # looking straight down
            s = np.array([1.0, 0.0, 0.0])
        s /= np.linalg.norm(s)
        u = np.cross(s, f)
        m = np.identity(4)
        m[0, :3], m[1, :3], m[2, :3] = s, u, -f
        m[:3, 3] = -m[:3, :3] @ eye
        return m

    def projection(self, aspect: float) -> F:
        near, far = max(self.distance * 0.01, 0.05), self.distance * 20 + 100
        f = 1 / math.tan(math.radians(self.fov) / 2)
        m = np.zeros((4, 4))
        m[0, 0], m[1, 1] = f / aspect, f
        m[2, 2], m[2, 3] = (far + near) / (near - far), 2 * far * near / (near - far)
        m[3, 2] = -1
        return m

    def matrix(self, width: int, height: int) -> F:
        return self.projection(width / max(height, 1)) @ self.view()

    # ---------------------------------------------------------- movement

    def orbit(self, d_yaw: float, d_pitch: float) -> None:
        self.yaw = (self.yaw + d_yaw) % 360
        self.pitch = min(max(self.pitch + d_pitch, -89.0), 89.0)

    def zoom(self, factor: float) -> None:
        self.distance = min(max(self.distance * factor, 0.5), 100000.0)

    def pan(self, dx_px: float, dy_px: float, height_px: int) -> None:
        """Move the target with the mouse: a drag across the view moves it by the visible
        width at the target's distance."""
        view = self.view()
        right, up = view[0, :3], view[1, :3]
        metres_per_px = 2 * self.distance * math.tan(math.radians(self.fov) / 2) / max(height_px, 1)
        self.target = self.target - right * dx_px * metres_per_px + up * dy_px * metres_per_px

    def fit(self, low: F, high: F) -> None:
        """Frame a bounding box."""
        self.target = (low + high) / 2
        radius = max(float(np.linalg.norm(high - low)) / 2, 1.0)
        self.distance = radius / math.sin(math.radians(self.fov) / 2) * 1.1

    def ray(self, x: float, y: float, width: int, height: int) -> tuple[F, F]:
        """Origin and unit direction of the ray through a widget pixel (y down)."""
        ndc = np.array([2 * x / width - 1, 1 - 2 * y / height, 1.0, 1.0])
        inverse = np.linalg.inv(self.matrix(width, height))
        far = inverse @ ndc
        far = far[:3] / far[3]
        eye = self.eye()
        direction = far - eye
        return eye, direction / np.linalg.norm(direction)


def ray_hit(
    origin: F, direction: F, vertices: F, triangles: NDArray[np.int32]
) -> tuple[int, float] | None:
    """Index of the nearest triangle hit by the ray and its distance (Moller-Trumbore)."""
    if len(triangles) == 0:
        return None
    v0, v1, v2 = (vertices[triangles[:, k]] for k in range(3))
    e1, e2 = v1 - v0, v2 - v0
    p = np.cross(direction, e2)
    det = np.einsum("ij,ij->i", e1, p)
    valid = np.abs(det) > 1e-12
    inv = np.where(valid, 1.0 / np.where(valid, det, 1.0), 0.0)
    t_vec = origin - v0
    u = np.einsum("ij,ij->i", t_vec, p) * inv
    q = np.cross(t_vec, e1)
    v = (q @ direction) * inv
    t = np.einsum("ij,ij->i", e2, q) * inv
    hit = valid & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)
    if not hit.any():
        return None
    index = int(np.argmin(np.where(hit, t, np.inf)))
    return index, float(t[index])
