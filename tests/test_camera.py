"""Orbit camera and ray picking (numpy only)."""

from __future__ import annotations

import numpy as np
import pytest

from brunelleschi.gui.camera import OrbitCamera, ray_hit

W, H = 800, 600


def project(cam: OrbitCamera, point: list[float]) -> np.ndarray:
    clip = cam.matrix(W, H) @ np.array([*point, 1.0])
    return np.asarray(clip[:3] / clip[3])


def test_fit_frames_the_box() -> None:
    cam = OrbitCamera.default()
    low, high = np.array([0.0, 0.0, 0.0]), np.array([6.0, 4.0, 3.0])
    cam.fit(low, high)
    assert cam.target == pytest.approx([3, 2, 1.5])
    for x in (0, 6):
        for y in (0, 4):
            for z in (0, 3):
                ndc = project(cam, [x, y, z])
                assert np.all(np.abs(ndc[:2]) < 1), (x, y, z, ndc)
                assert -1 < ndc[2] < 1


def test_target_is_at_the_centre_of_the_view() -> None:
    cam = OrbitCamera(target=np.array([1.0, 2.0, 3.0]), distance=10, yaw=30, pitch=20)
    assert project(cam, [1, 2, 3])[:2] == pytest.approx([0, 0], abs=1e-9)
    assert np.linalg.norm(cam.eye() - cam.target) == pytest.approx(10)


def test_ray_through_the_centre_points_at_the_target() -> None:
    cam = OrbitCamera(target=np.array([1.0, 2.0, 3.0]), distance=10, yaw=30, pitch=20)
    origin, direction = cam.ray(W / 2, H / 2, W, H)
    expected = cam.target - cam.eye()
    assert direction == pytest.approx(expected / np.linalg.norm(expected))
    assert origin == pytest.approx(cam.eye())


def test_orbit_limits_and_zoom() -> None:
    cam = OrbitCamera.default()
    cam.orbit(10, 200)
    assert cam.pitch == 89.0
    cam.orbit(400, -500)
    assert cam.pitch == -89.0
    assert 0 <= cam.yaw < 360
    cam.zoom(0.5)
    assert cam.distance == 10.0


def test_pan_moves_the_target_in_the_view_plane() -> None:
    cam = OrbitCamera(target=np.zeros(3), distance=10, yaw=0, pitch=0)  # looking north
    cam.pan(100, 0, H)  # dragging right moves the scene right, the target left
    assert cam.target[0] < 0
    assert cam.target[1] == pytest.approx(0)
    assert cam.target[2] == pytest.approx(0)


def test_ray_hit_returns_the_nearest_triangle() -> None:
    vertices = np.array(
        [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1]], dtype=float
    )
    triangles = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int32)
    hit = ray_hit(np.array([0.2, 0.2, 5.0]), np.array([0, 0, -1.0]), vertices, triangles)
    assert hit is not None
    index, distance = hit
    assert index == 1
    assert distance == pytest.approx(4.0)
    assert ray_hit(np.array([2.0, 2.0, 5.0]), np.array([0, 0, -1.0]), vertices, triangles) is None
    assert ray_hit(np.array([0.2, 0.2, -1.0]), np.array([0, 0, -1.0]), vertices, triangles) is None
