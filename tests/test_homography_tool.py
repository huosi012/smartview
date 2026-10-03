import numpy as np
import pytest

from smartview.geometry.camera import PinholeCamera
from smartview.tools.homography import parse_points, solve_homography


def test_solve_from_synthetic_points():
    cam = PinholeCamera.from_fov(1920, 1080, 60, x_fwd_m=-2.5, z_m=3.2, pitch_deg=15)
    ground = [(5, -2), (5, 2), (10, -2.5), (10, 2.5), (15, 0), (20, 1)]
    px = [cam.ground_to_image(x, y) for x, y in ground]
    H, rms = solve_homography(px, ground)
    assert rms < 1e-6
    for (u, v), (x, y) in zip(px, ground, strict=True):
        p = H @ np.array([u, v, 1.0])
        assert abs(p[0] / p[2] - x) < 1e-6 and abs(p[1] / p[2] - y) < 1e-6
    with pytest.raises(ValueError):
        solve_homography(px[:3], ground[:3])


def test_parse_points():
    px, gd = parse_points("960,900,5,0; 300,700,10,-2;")
    assert px == [(960.0, 900.0), (300.0, 700.0)] and gd == [(5.0, 0.0), (10.0, -2.0)]
