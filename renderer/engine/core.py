#!/usr/bin/env python3
"""Core CPU SDF ray-marching renderer primitives and render pipeline."""

import math
import os
import struct
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Callable, Dict, Optional, Tuple

from ..common.color_utils import color_to_bytes, gamma_correct, to_unit_color
from ..common.math_utils import add, clamp, cross, dot, length, length2, length8, mix, mul, normalize, sub
from ..common.types import Color, Vec3
from .constants import (
    BOX_CENTER,
    BOX_HALF_SIZE,
    CONE_BASE_RADIUS,
    CONE_CENTER,
    CONE_HALF_HEIGHT,
    CONE_TOP_RADIUS,
    MAT_BOX,
    MAT_CONE,
    MAT_NONE,
    MAT_PLANE,
    MAT_SPHERE,
    MAT_TORUS,
    MAT_TORUS82,
    MAT_TUBE,
    SPHERE_CENTER,
    SPHERE_RADIUS,
    TORUS82_RADII,
    TORUS_RADII,
    TUBE_CENTER,
    TUBE_HALF_HEIGHT,
    TUBE_RADIUS,
    WHEEL_CENTER,
    WHEEL_SMOOTH_K,
)
# SDF primitives
# -----------------------------
def sd_plane(p: Vec3) -> float:
    """Signed distance to plane y = -1 (positive above plane).

    Args:
        p (Vec3): P value.

    Returns:
        float: Computed result.
    """
    return p[1] + 1.0


def sd_sphere(p: Vec3, c: Vec3, r: float) -> float:
    """Signed distance to sphere centered at c with radius r.

    Args:
        p (Vec3): P value.
        c (Vec3): C value.
        r (float): R value.

    Returns:
        float: Computed result.
    """
    return length(sub(p, c)) - r


def sd_box(p: Vec3, c: Vec3, b: Vec3) -> float:
    """Signed distance to axis-aligned box (center c, half-extents b).

    Args:
        p (Vec3): P value.
        c (Vec3): C value.
        b (Vec3): B value.

    Returns:
        float: Computed result.
    """
    q = sub(p, c)
    qx = abs(q[0]) - b[0]
    qy = abs(q[1]) - b[1]
    qz = abs(q[2]) - b[2]

    ox = max(qx, 0.0)
    oy = max(qy, 0.0)
    oz = max(qz, 0.0)
    # Outside term handles distance to nearest exterior corner/edge/face.
    outside = math.sqrt(ox * ox + oy * oy + oz * oz)
    # Inside term keeps SDF negative when point is inside the box volume.
    inside = min(max(qx, max(qy, qz)), 0.0)
    return outside + inside


def sd_torus(p: Vec3, c: Vec3, t: Tuple[float, float]) -> float:
    """Distance to classic torus around Y axis: t=(major_radius, minor_radius).

    Args:
        p (Vec3): P value.
        c (Vec3): C value.
        t (Tuple[float, float]): T value.

    Returns:
        float: Computed result.
    """
    q = sub(p, c)
    x = length2((q[0], q[2])) - t[0]
    return length2((x, q[1])) - t[1]


def sd_torus82(p: Vec3, c: Vec3, t: Tuple[float, float]) -> float:
    """Distance to 'boxier' torus variant using L^8 norm in cross section.

    Args:
        p (Vec3): P value.
        c (Vec3): C value.
        t (Tuple[float, float]): T value.

    Returns:
        float: Computed result.
    """
    q = sub(p, c)
    x = length2((q[0], q[2])) - t[0]
    return length8((x, q[1])) - t[1]


def sd_capped_cone(p: Vec3, c: Vec3, h: float, r1: float, r2: float) -> float:
    """Distance to a finite cone frustum capped at both ends.

    Args:
        p (Vec3): P value.
        c (Vec3): C value.
        h (float): H value.
        r1 (float): R1 value.
        r2 (float): R2 value.

    Returns:
        float: Computed result.
    """
    # Exact capped-cone SDF (axis: +Y, local range y in [-h, +h]).
    q = sub(p, c)
    q2 = (length2((q[0], q[2])), q[1])
    k1 = (r2, h)
    k2 = (r2 - r1, 2.0 * h)

    cap_radius = r1 if q2[1] < 0.0 else r2
    ca = (q2[0] - min(q2[0], cap_radius), abs(q2[1]) - h)

    k1_minus_q2 = (k1[0] - q2[0], k1[1] - q2[1])
    k2_dot = k2[0] * k2[0] + k2[1] * k2[1]
    t = clamp((k1_minus_q2[0] * k2[0] + k1_minus_q2[1] * k2[1]) / k2_dot, 0.0, 1.0)
    cb = (q2[0] - k1[0] + k2[0] * t, q2[1] - k1[1] + k2[1] * t)

    ca2 = ca[0] * ca[0] + ca[1] * ca[1]
    cb2 = cb[0] * cb[0] + cb[1] * cb[1]
    # Sign chooses inside (-) vs outside (+) distance.
    inside_sign = -1.0 if (cb[0] < 0.0 and ca[1] < 0.0) else 1.0
    return inside_sign * math.sqrt(min(ca2, cb2))


def sd_capped_cylinder(p: Vec3, c: Vec3, h: float, r: float) -> float:
    """Distance to finite vertical cylinder (center c, half-height h, radius r).

    Args:
        p (Vec3): P value.
        c (Vec3): C value.
        h (float): H value.
        r (float): R value.

    Returns:
        float: Computed result.
    """
    q = sub(p, c)
    d = (length2((q[0], q[2])) - r, abs(q[1]) - h)
    outside = length2((max(d[0], 0.0), max(d[1], 0.0)))
    inside = min(max(d[0], d[1]), 0.0)
    return outside + inside


def smooth_union(d1: float, d2: float, k: float) -> float:
    """Blend two SDFs smoothly; larger k means softer transition.

    Args:
        d1 (float): D1 value.
        d2 (float): D2 value.
        k (float): K value.

    Returns:
        float: Computed result.
    """
    if k <= 0.0:
        return min(d1, d2)
    h = clamp(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0)
    return mix(d2, d1, h) - k * h * (1.0 - h)


def wheel_distance_and_material(p: Vec3) -> Tuple[float, int]:
    """Wheel is a smooth union of two torus profiles; return (distance, dominant material).

    Args:
        p (Vec3): P value.

    Returns:
        Tuple[float, int]: Tuple containing computed values.
    """
    d_torus = sd_torus(p, WHEEL_CENTER, TORUS_RADII)
    d_torus82 = sd_torus82(p, WHEEL_CENTER, TORUS82_RADII)
    d_wheel = smooth_union(d_torus, d_torus82, WHEEL_SMOOTH_K)
    wheel_mat = MAT_TORUS if d_torus < d_torus82 else MAT_TORUS82
    return d_wheel, wheel_mat


def map_objects(p: Vec3) -> Tuple[float, int]:
    """Return nearest object distance/material at point p.

    Args:
        p (Vec3): P value.

    Returns:
        Tuple[float, int]: Tuple containing computed values.
    """
    # Brute-force minimum across all finite objects in the scene.
    best_d = float("inf")
    best_m = MAT_NONE

    d_sphere = sd_sphere(p, SPHERE_CENTER, SPHERE_RADIUS)
    if d_sphere < best_d:
        best_d = d_sphere
        best_m = MAT_SPHERE

    d_box = sd_box(p, BOX_CENTER, BOX_HALF_SIZE)
    if d_box < best_d:
        best_d = d_box
        best_m = MAT_BOX

    d_wheel, wheel_mat = wheel_distance_and_material(p)
    if d_wheel < best_d:
        best_d = d_wheel
        best_m = wheel_mat

    d_cone = sd_capped_cone(p, CONE_CENTER, CONE_HALF_HEIGHT, CONE_BASE_RADIUS, CONE_TOP_RADIUS)
    if d_cone < best_d:
        best_d = d_cone
        best_m = MAT_CONE

    d_tube = sd_capped_cylinder(p, TUBE_CENTER, TUBE_HALF_HEIGHT, TUBE_RADIUS)
    if d_tube < best_d:
        best_d = d_tube
        best_m = MAT_TUBE

    return best_d, best_m


def march_objects(ro: Vec3, rd: Vec3, max_steps: int, max_dist: float, eps: float) -> Tuple[bool, float, int]:
    """Sphere-tracing pass against finite objects only (no ground plane).

    Args:
        ro (Vec3): Ro value.
        rd (Vec3): Rd value.
        max_steps (int): Max steps value.
        max_dist (float): Max dist value.
        eps (float): Eps value.

    Returns:
        Tuple[bool, float, int]: Tuple containing computed values.
    """
    t = 0.0
    for _ in range(max_steps):
        # Sample SDF at current ray position.
        p = add(ro, mul(rd, t))
        d, mat = map_objects(p)
        if d < eps:
            return True, t, mat
        # Safe sphere-tracing step: move by the reported distance.
        t += d
        if t > max_dist:
            break
    return False, t, MAT_NONE


def intersect_plane(ro: Vec3, rd: Vec3) -> Optional[float]:
    """Analytic intersection with the infinite ground plane y = -1.

    Args:
        ro (Vec3): Ro value.
        rd (Vec3): Rd value.

    Returns:
        Optional[float]: Computed value if available; otherwise None.
    """
    denom = rd[1]
    if abs(denom) < 1e-12:
        return None
    t = (-1.0 - ro[1]) / denom
    if t > 0.0:
        return t
    return None


def trace_scene(ro: Vec3, rd: Vec3, max_steps: int, max_dist: float, eps: float) -> Tuple[bool, float, int]:
    """Combine object marching + plane hit, then pick nearest valid hit.

    Args:
        ro (Vec3): Ro value.
        rd (Vec3): Rd value.
        max_steps (int): Max steps value.
        max_dist (float): Max dist value.
        eps (float): Eps value.

    Returns:
        Tuple[bool, float, int]: Tuple containing computed values.
    """
    obj_hit, obj_t, obj_mat = march_objects(ro, rd, max_steps, max_dist, eps)
    plane_t = intersect_plane(ro, rd)
    plane_hit = plane_t is not None and plane_t <= max_dist

    # If both were hit, prefer whichever intersection is closer.
    if (obj_hit and plane_hit) and plane_t is not None and obj_t is not None:
        if obj_t <= plane_t + eps * 2.0:
            return True, obj_t, obj_mat
        return True, plane_t, MAT_PLANE
    if obj_hit:
        return True, obj_t, obj_mat
    if plane_hit and plane_t is not None:
        return True, plane_t, MAT_PLANE
    return False, max_dist, MAT_NONE


def distance_for_material(p: Vec3, mat_id: int) -> float:
    """Distance function for one specific material (used for normal estimation).

    Args:
        p (Vec3): P value.
        mat_id (int): Mat id value.

    Returns:
        float: Computed result.
    """
    if mat_id == MAT_PLANE:
        return sd_plane(p)
    if mat_id == MAT_SPHERE:
        return sd_sphere(p, SPHERE_CENTER, SPHERE_RADIUS)
    if mat_id == MAT_BOX:
        return sd_box(p, BOX_CENTER, BOX_HALF_SIZE)
    if mat_id == MAT_TORUS or mat_id == MAT_TORUS82:
        return wheel_distance_and_material(p)[0]
    if mat_id == MAT_CONE:
        return sd_capped_cone(p, CONE_CENTER, CONE_HALF_HEIGHT, CONE_BASE_RADIUS, CONE_TOP_RADIUS)
    if mat_id == MAT_TUBE:
        return sd_capped_cylinder(p, TUBE_CENTER, TUBE_HALF_HEIGHT, TUBE_RADIUS)
    return map_objects(p)[0]


def estimate_normal(p: Vec3, eps: float, mat_id: int) -> Vec3:
    """Estimate geometric normal from SDF gradient with central differences.

    Args:
        p (Vec3): P value.
        eps (float): Eps value.
        mat_id (int): Mat id value.

    Returns:
        Vec3: Computed value.
    """
    if mat_id == MAT_PLANE:
        # Plane normal is constant, so avoid unnecessary sampling.
        return (0.0, 1.0, 0.0)

    ex = (eps, 0.0, 0.0)
    ey = (0.0, eps, 0.0)
    ez = (0.0, 0.0, eps)

    dx = distance_for_material(add(p, ex), mat_id) - distance_for_material(sub(p, ex), mat_id)
    dy = distance_for_material(add(p, ey), mat_id) - distance_for_material(sub(p, ey), mat_id)
    dz = distance_for_material(add(p, ez), mat_id) - distance_for_material(sub(p, ez), mat_id)
    return normalize((dx, dy, dz))


def scene_distance(p: Vec3) -> float:
    """Global SDF used by AO queries (objects + plane).

    Args:
        p (Vec3): P value.

    Returns:
        float: Computed result.
    """
    return min(sd_plane(p), map_objects(p)[0])


def calc_soft_shadow(ro: Vec3, rd: Vec3, t_min: float, t_max: float, shadow_steps: int) -> float:
    """Approximate soft shadow by secondary marching toward the key light.

    Args:
        ro (Vec3): Ro value.
        rd (Vec3): Rd value.
        t_min (float): T min value.
        t_max (float): T max value.
        shadow_steps (int): Shadow steps value.

    Returns:
        float: Computed result.
    """
    # March only against object SDF to avoid self-shadowing from the infinite plane.
    if shadow_steps <= 0:
        return 1.0
    res = 1.0
    t = t_min
    for _ in range(shadow_steps):
        if t > t_max:
            break
        # Query blocker distance along shadow ray.
        h = map_objects(add(ro, mul(rd, t)))[0]
        if h < 0.0007:
            return 0.0
        res = min(res, 8.0 * h / max(t, 1e-4))
        t += clamp(h, 0.01, 0.22)
    res = clamp(res, 0.0, 1.0)
    return res * res * (3.0 - 2.0 * res)


def calc_ambient_occlusion(pos: Vec3, nor: Vec3, ao_samples: int) -> float:
    """Estimate ambient occlusion by probing along the surface normal.

    Args:
        pos (Vec3): Pos value.
        nor (Vec3): Nor value.
        ao_samples (int): Ao samples value.

    Returns:
        float: Computed result.
    """
    if ao_samples <= 0:
        return 1.0
    occ = 0.0
    sca = 1.0
    span = max(ao_samples - 1, 1)
    for i in range(ao_samples):
        # Probe distances increase gradually away from the surface.
        h = 0.02 + 0.10 * (i / span)
        d = scene_distance(add(pos, mul(nor, h)))
        occ += (h - d) * sca
        sca *= 0.92
    # Convert accumulated occlusion into final attenuation factor.
    ao = clamp(1.0 - 2.8 * occ, 0.0, 1.0)
    return ao * (0.55 + 0.45 * clamp(0.5 + 0.5 * nor[1], 0.0, 1.0))


def material_spec(mat_id: int) -> Tuple[float, float]:
    """Material-specific highlight controls: (specular strength, shininess).

    Args:
        mat_id (int): Mat id value.

    Returns:
        Tuple[float, float]: Tuple containing computed values.
    """
    # (spec_strength, shininess)
    if mat_id == MAT_PLANE:
        return 0.15, 28.0
    if mat_id == MAT_SPHERE:
        return 0.58, 90.0
    if mat_id == MAT_BOX:
        return 0.34, 44.0
    if mat_id == MAT_TORUS or mat_id == MAT_TORUS82:
        return 0.64, 96.0
    if mat_id == MAT_CONE:
        return 0.28, 34.0
    if mat_id == MAT_TUBE:
        return 0.48, 66.0
    return 0.25, 40.0


def sky_color(rd: Vec3) -> Color:
    """Simple vertical sky gradient used for misses and fog tinting.

    Args:
        rd (Vec3): Rd value.

    Returns:
        Color: Computed value.
    """
    t = clamp(0.5 * (rd[1] + 1.0), 0.0, 1.0)
    return (
        mix(0.90, 0.45, t),
        mix(0.95, 0.66, t),
        mix(1.00, 0.98, t),
    )


def gamma_correct(c: Color) -> Color:
    """Convert from linear color space to display-ish gamma space.

    Args:
        c (Color): C value.

    Returns:
        Color: Computed value.
    """
    inv_gamma = 1.0 / 2.2
    return (
        clamp(c[0], 0.0, 1.0) ** inv_gamma,
        clamp(c[1], 0.0, 1.0) ** inv_gamma,
        clamp(c[2], 0.0, 1.0) ** inv_gamma,
    )


def color_to_bytes(c: Color) -> Tuple[int, int, int]:
    """Convert normalized RGB [0..1] to 8-bit RGB [0..255].

    Args:
        c (Color): C value.

    Returns:
        Tuple[int, int, int]: Tuple containing computed values.
    """
    r = int(clamp(c[0], 0.0, 1.0) * 255.0 + 0.5)
    g = int(clamp(c[1], 0.0, 1.0) * 255.0 + 0.5)
    b = int(clamp(c[2], 0.0, 1.0) * 255.0 + 0.5)
    return r, g, b


def shade(
    hit_point: Vec3,
    mat_id: int,
    rd: Vec3,
    mat_colors: Dict[int, Color],
    eps: float,
    hit_dist: float,
    max_dist: float,
    shadow_steps: int,
    ao_samples: int,
) -> Color:
    """Compute final shaded color for one surface hit point.

    Args:
        hit_point (Vec3): Hit point value.
        mat_id (int): Mat id value.
        rd (Vec3): Rd value.
        mat_colors (Dict[int, Color]): Mat colors value.
        eps (float): Eps value.
        hit_dist (float): Hit dist value.
        max_dist (float): Max dist value.
        shadow_steps (int): Shadow steps value.
        ao_samples (int): Ao samples value.

    Returns:
        Color: Computed value.
    """
    # 1) Surface basis vectors.
    normal = estimate_normal(hit_point, eps * 2.0, mat_id)
    view_dir = mul(rd, -1.0)

    # 2) Lighting rig: key/fill/rim directions and colors.
    key_dir = normalize((-0.52, 0.72, -0.46))
    fill_dir = normalize((0.64, 0.28, 0.72))
    rim_dir = normalize((0.20, 0.10, 0.97))

    # Slightly warm key + cool fill produces better visual depth.
    key_col = (1.00, 0.96, 0.87)
    fill_col = (0.52, 0.62, 0.90)

    shadow = 1.0
    key_ndl = max(dot(normal, key_dir), 0.0)
    if key_ndl > 0.0:
        # Offset origin slightly along the normal to reduce acne.
        shadow = calc_soft_shadow(add(hit_point, mul(normal, eps * 6.0)), key_dir, 0.02, 20.0, shadow_steps)

    # 3) AO darkens crevices and grounded surfaces.
    ao = calc_ambient_occlusion(hit_point, normal, ao_samples)

    key_diff = key_ndl * shadow
    fill_diff = max(dot(normal, fill_dir), 0.0)
    rim_diff = max(dot(normal, rim_dir), 0.0)

    base = mat_colors[mat_id]
    if mat_id == MAT_PLANE:
        # Add subtle checker variation on the ground for depth cues.
        checker = (int(math.floor(hit_point[0] * 1.2)) + int(math.floor(hit_point[2] * 1.2))) & 1
        checker_mul = 0.88 if checker else 1.08
        base = (
            clamp(base[0] * checker_mul, 0.0, 1.0),
            clamp(base[1] * checker_mul, 0.0, 1.0),
            clamp(base[2] * checker_mul, 0.0, 1.0),
        )

    # Hemisphere term fakes broad environment lighting from above.
    hemi = 0.22 + 0.34 * clamp(0.5 + 0.5 * normal[1], 0.0, 1.0)
    diffuse_r = key_col[0] * (1.20 * key_diff) + fill_col[0] * (0.40 * fill_diff)
    diffuse_g = key_col[1] * (1.20 * key_diff) + fill_col[1] * (0.40 * fill_diff)
    diffuse_b = key_col[2] * (1.20 * key_diff) + fill_col[2] * (0.40 * fill_diff)

    # Material controls determine highlight strength + glossiness exponent.
    spec_strength, shininess = material_spec(mat_id)
    half_key = normalize(add(key_dir, view_dir))
    key_spec = (max(dot(normal, half_key), 0.0) ** shininess) * spec_strength * shadow
    half_fill = normalize(add(fill_dir, view_dir))
    fill_spec = (max(dot(normal, half_fill), 0.0) ** (shininess * 0.55)) * (spec_strength * 0.22)

    # Fresnel-like term boosts edge lighting toward glancing view angles.
    fresnel = (1.0 - max(dot(normal, view_dir), 0.0)) ** 5.0
    sky = sky_color(rd)
    rim = rim_diff * (0.08 + 0.12 * fresnel) * ao

    # 4) Combine diffuse + specular + rim.
    lit = (
        base[0] * ao * (hemi + diffuse_r) + key_col[0] * key_spec + fill_col[0] * fill_spec + sky[0] * rim,
        base[1] * ao * (hemi + diffuse_g) + key_col[1] * key_spec + fill_col[1] * fill_spec + sky[1] * rim,
        base[2] * ao * (hemi + diffuse_b) + key_col[2] * key_spec + fill_col[2] * fill_spec + sky[2] * rim,
    )

    # 5) Distance fog blends toward sky with hit distance.
    # Mild atmospheric attenuation with distance.
    fog = clamp((hit_dist / max_dist) ** 1.3, 0.0, 1.0) * 0.18
    sky = sky_color(rd)
    return (
        mix(lit[0], sky[0], fog),
        mix(lit[1], sky[1], fog),
        mix(lit[2], sky[2], fog),
    )


def to_unit_color(rgb: Tuple[int, int, int]) -> Color:
    """Convert 8-bit RGB tuple into normalized float color.

    Args:
        rgb (Tuple[int, int, int]): Rgb value.

    Returns:
        Color: Computed value.
    """
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def build_material_colors(args: Any) -> Dict[int, Color]:
    """Build material-color table from CLI/GUI-selected colors.

    Args:
        args (Any): Parsed application arguments.

    Returns:
        Dict[int, Color]: Computed value.
    """
    return {
        MAT_PLANE: to_unit_color(tuple(args.plane_color)),
        MAT_SPHERE: to_unit_color(tuple(args.sphere_color)),
        MAT_BOX: to_unit_color(tuple(args.box_color)),
        MAT_TORUS: to_unit_color(tuple(args.torus_color)),
        MAT_TORUS82: to_unit_color(tuple(args.torus82_color)),
        MAT_CONE: to_unit_color(tuple(args.cone_color)),
        MAT_TUBE: to_unit_color(tuple(args.tube_color)),
    }


def resolve_worker_count(workers: int) -> int:
    """Resolve requested worker count (0 => auto).

    Args:
        workers (int): Workers value.

    Returns:
        int: Computed result.
    """
    if workers <= 0:
        return max(1, int(os.cpu_count() or 1))
    return workers


def render_row(
    y: int,
    width: int,
    height: int,
    aa: int,
    cam_pos: Vec3,
    right: Vec3,
    cam_up: Vec3,
    forward: Vec3,
    aspect: float,
    scale: float,
    max_steps: int,
    max_dist: float,
    eps: float,
    shadow_steps: int,
    ao_samples: int,
    mat_colors: Dict[int, Color],
) -> Tuple[int, bytes]:
    """Render one scanline and return (row_index, row_rgb_bytes).

    Args:
        y (int): y coordinate value.
        width (int): Width input value.
        height (int): Height input value.
        aa (int): Aa value.
        cam_pos (Vec3): Cam pos value.
        right (Vec3): Right value.
        cam_up (Vec3): Cam up value.
        forward (Vec3): Forward value.
        aspect (float): Aspect value.
        scale (float): Scale value.
        max_steps (int): Max steps value.
        max_dist (float): Max dist value.
        eps (float): Eps value.
        shadow_steps (int): Shadow steps value.
        ao_samples (int): Ao samples value.
        mat_colors (Dict[int, Color]): Mat colors value.

    Returns:
        Tuple[int, bytes]: Tuple containing computed values.
    """
    # AA uses an aa x aa regular grid of sub-pixel samples.
    sample_count = aa * aa
    inv_samples = 1.0 / sample_count
    row = bytearray(width * 3)
    index = 0

    for x in range(width):
        # Accumulate all sub-samples in linear color space.
        acc_r = 0.0
        acc_g = 0.0
        acc_b = 0.0
        for sy in range(aa):
            # Convert pixel row + sub-sample to normalized screen-space Y.
            v = (sy + 0.5) / aa
            py = (1.0 - 2.0 * ((y + v) / height)) * scale
            for sx in range(aa):
                # Convert pixel column + sub-sample to normalized screen-space X.
                u = (sx + 0.5) / aa
                px = (2.0 * ((x + u) / width) - 1.0) * aspect * scale
                # Build world-space ray direction from camera basis.
                rd = normalize(add(add(mul(right, px), mul(cam_up, py)), forward))

                hit, hit_dist, mat_id = trace_scene(
                    cam_pos,
                    rd,
                    max_steps,
                    max_dist,
                    eps,
                )

                if hit:
                    # March hit: evaluate physically-inspired shading model.
                    hit_point = add(cam_pos, mul(rd, hit_dist))
                    color = shade(
                        hit_point,
                        mat_id,
                        rd,
                        mat_colors,
                        eps,
                        hit_dist,
                        max_dist,
                        shadow_steps,
                        ao_samples,
                    )
                else:
                    # Miss: sample background sky gradient.
                    color = sky_color(rd)
                acc_r += color[0]
                acc_g += color[1]
                acc_b += color[2]

        # Average samples, gamma-correct, and quantize to output bytes.
        color = gamma_correct((acc_r * inv_samples, acc_g * inv_samples, acc_b * inv_samples))
        r, g, b = color_to_bytes(color)
        row[index] = r
        row[index + 1] = g
        row[index + 2] = b
        index += 3

    return y, bytes(row)


def render_image(
    args: Any,
    row_callback: Optional[Callable[[int, bytearray, float], None]] = None,
    disable_terminal_progress: bool = False,
) -> bytearray:
    """Main CPU renderer with optional multi-worker parallelism.

    Args:
        args (Any): Parsed application arguments.
        row_callback (Optional[Callable[[int, bytearray, float], None]]): Row callback value.
        disable_terminal_progress (bool): Disable terminal progress value.

    Returns:
        bytearray: Computed value.
    """
    # Pull frequently used args into locals for speed/readability.
    width = args.width
    height = args.height
    aa = args.aa
    workers = resolve_worker_count(int(getattr(args, "workers", 1)))
    show_progress = (not args.no_progress) and (not disable_terminal_progress)
    progress_start = time.perf_counter()
    last_progress_permille = -1

    cam_pos = tuple(args.cam_pos)
    cam_target = tuple(args.cam_target)
    cam_up_input = tuple(args.cam_up)

    # Camera basis vectors for transforming screen-space rays to world-space.
    forward = normalize(sub(cam_target, cam_pos))
    right = normalize(cross(cam_up_input, forward))
    cam_up = cross(forward, right)

    # Perspective projection scale from vertical field of view.
    aspect = width / height
    scale = math.tan(math.radians(args.fov) * 0.5)

    mat_colors = build_material_colors(args)
    pixels = bytearray(width * height * 3)
    row_bytes = width * 3

    # Initialize progress output and optional GUI callback.
    if show_progress:
        print_progress(0, height, progress_start)
    if row_callback is not None:
        row_callback(0, pixels, progress_start)

    done_rows = 0
    if workers <= 1 or height <= 1:
        # Single-worker path (kept simple and deterministic).
        for y in range(height):
            row_y, row_data = render_row(
                y,
                width,
                height,
                aa,
                cam_pos,
                right,
                cam_up,
                forward,
                aspect,
                scale,
                args.max_steps,
                args.max_dist,
                args.eps,
                args.shadow_steps,
                args.ao_samples,
                mat_colors,
            )
            start = row_y * row_bytes
            pixels[start:start + row_bytes] = row_data
            done_rows += 1

            if show_progress:
                progress_permille = int(done_rows * 1000 / height)
                if progress_permille != last_progress_permille or done_rows == height:
                    print_progress(done_rows, height, progress_start)
                    last_progress_permille = progress_permille
            if row_callback is not None:
                # Gives GUI a chance to refresh preview/progress.
                row_callback(done_rows, pixels, progress_start)
    else:
        # Multi-worker path (process pool for actual CPU parallelism).
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    render_row,
                    y,
                    width,
                    height,
                    aa,
                    cam_pos,
                    right,
                    cam_up,
                    forward,
                    aspect,
                    scale,
                    args.max_steps,
                    args.max_dist,
                    args.eps,
                    args.shadow_steps,
                    args.ao_samples,
                    mat_colors,
                )
                for y in range(height)
            ]

            for future in as_completed(futures):
                # Futures complete out of order; row_y places data correctly.
                row_y, row_data = future.result()
                start = row_y * row_bytes
                pixels[start:start + row_bytes] = row_data
                done_rows += 1

                if show_progress:
                    progress_permille = int(done_rows * 1000 / height)
                    if progress_permille != last_progress_permille or done_rows == height:
                        print_progress(done_rows, height, progress_start)
                        last_progress_permille = progress_permille
                if row_callback is not None:
                    row_callback(done_rows, pixels, progress_start)

    return pixels


def print_progress(done_rows: int, total_rows: int, start_time: float) -> None:
    """Print a single-line terminal progress bar.

    Args:
        done_rows (int): Number of completed rows.
        total_rows (int): Total rows in the render.
        start_time (float): ``time.perf_counter()`` timestamp at render start.

    Returns:
        None: This function does not return a value.
    """
    if total_rows <= 0:
        return
    percent = (100.0 * done_rows) / total_rows
    bar_width = 32
    filled = int(bar_width * done_rows / total_rows)
    bar = "#" * filled + "-" * (bar_width - filled)
    elapsed = time.perf_counter() - start_time
    end_char = "\n" if done_rows >= total_rows else ""
    print(
        f"\rRendering [{bar}] {percent:6.2f}% ({done_rows}/{total_rows} rows, {elapsed:.1f}s)",
        end=end_char,
        flush=True,
        file=sys.stdout,
    )


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build one PNG chunk with length/type/data/CRC.

    Args:
        chunk_type (bytes): Chunk type value.
        data (bytes): Data value.

    Returns:
        bytes: Computed value.
    """
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", crc)
    )


def write_png(path: str, width: int, height: int, pixels: bytearray) -> None:
    """Write RGB buffer as PNG using only stdlib (zlib + struct).

    Args:
        path (str): Path input value.
        width (int): Width input value.
        height (int): Height input value.
        pixels (bytearray): Pixels input value.

    Returns:
        None: This function does not return a value.
    """
    raw = bytearray()
    row_bytes = width * 3
    for y in range(height):
        # PNG requires a filter byte before each scanline (0 => no filter).
        start = y * row_bytes
        end = start + row_bytes
        raw.append(0)
        raw.extend(pixels[start:end])

    # Compress image payload and emit minimal PNG chunks.
    compressed = zlib.compress(bytes(raw), level=9)
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    with open(path, "wb") as f:
        f.write(signature)
        f.write(png_chunk(b"IHDR", ihdr))
        f.write(png_chunk(b"IDAT", compressed))
        f.write(png_chunk(b"IEND", b""))


def write_image(path: str, width: int, height: int, pixels: bytearray) -> None:
    """Write rendered pixels as PNG.

    Args:
        path (str): Path input value.
        width (int): Width input value.
        height (int): Height input value.
        pixels (bytearray): Pixels input value.

    Returns:
        None: This function does not return a value.
    """
    lower = path.lower()
    if not lower.endswith(".png"):
        raise ValueError("Output extension must be .png.")
    write_png(path, width, height, pixels)

