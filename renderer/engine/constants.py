#!/usr/bin/env python3
"""Project constants: defaults, scene layout, materials, and quality presets."""

from ..common.types import Vec3

# -----------------------------
# Defaults
# -----------------------------
DEFAULT_OUTPUT = "cpu-sdf-raymarch-output.png"
DEFAULT_WIDTH = 400
DEFAULT_HEIGHT = 225

DEFAULT_CAM_POS: Vec3 = (-1.4, 1.25, -4.4)
DEFAULT_CAM_TARGET: Vec3 = (-1.4, -0.25, 4.6)
DEFAULT_CAM_UP: Vec3 = (0.0, 1.0, 0.0)
DEFAULT_FOV = 46.0

DEFAULT_QUALITY = "balanced"
RESOLUTION_OPTIONS = [
    ("640x360", 640, 360),
    ("800x450", 800, 450),
    ("960x540", 960, 540),
    ("1280x720", 1280, 720),
    ("1920x1080", 1920, 1080),
]

QUALITY_PRESETS: dict[str, dict[str, float | int]] = {
    "draft": {
        "aa": 1,
        "max_steps": 120,
        "max_dist": 45.0,
        "eps": 0.0015,
        "shadow_steps": 8,
        "ao_samples": 2,
        "preview_every": 12,
    },
    "balanced": {
        "aa": 1,
        "max_steps": 170,
        "max_dist": 60.0,
        "eps": 0.0010,
        "shadow_steps": 14,
        "ao_samples": 3,
        "preview_every": 8,
    },
    "high": {
        "aa": 2,
        "max_steps": 220,
        "max_dist": 75.0,
        "eps": 0.0008,
        "shadow_steps": 20,
        "ao_samples": 5,
        "preview_every": 4,
    },
}

DEFAULT_PLANE_COLOR = (165, 186, 205)
DEFAULT_SPHERE_COLOR = (236, 115, 93)
DEFAULT_BOX_COLOR = (102, 196, 174)
DEFAULT_TORUS_COLOR = (255, 198, 79)
DEFAULT_TORUS82_COLOR = (198, 143, 255)
DEFAULT_CONE_COLOR = (255, 161, 99)
DEFAULT_TUBE_COLOR = (96, 210, 255)

# -----------------------------
# Material IDs
# -----------------------------
MAT_NONE = 0
MAT_PLANE = 1
MAT_SPHERE = 2
MAT_BOX = 3
MAT_TORUS = 4
MAT_TORUS82 = 5
MAT_CONE = 6
MAT_TUBE = 7

# -----------------------------
# Scene layout
# -----------------------------
SPHERE_CENTER: Vec3 = (-5.8, -0.16, 4.6)
SPHERE_RADIUS = 0.85

BOX_CENTER: Vec3 = (-3.6, -0.26, 4.6)
BOX_HALF_SIZE: Vec3 = (0.75, 0.75, 0.75)

WHEEL_CENTER: Vec3 = (-1.4, -0.67, 4.6)
TORUS_RADII = (0.82, 0.34)
TORUS82_RADII = (0.82, 0.24)
WHEEL_SMOOTH_K = 0.06

CONE_CENTER: Vec3 = (0.8, -0.06, 4.6)
CONE_HALF_HEIGHT = 0.95
CONE_BASE_RADIUS = 0.62
CONE_TOP_RADIUS = 0.04

TUBE_CENTER: Vec3 = (3.0, -0.11, 4.6)
TUBE_RADIUS = 0.55
TUBE_HALF_HEIGHT = 0.9
