#!/usr/bin/env python3
"""Math helpers used by renderer modules."""

import math
from typing import Tuple

from .types import Vec3


def add(a: Vec3, b: Vec3) -> Vec3:
    """Component-wise vector addition.

    Args:
        a (Vec3): Left vector.
        b (Vec3): Right vector.

    Returns:
        Vec3: Summed vector.
    """
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec3, b: Vec3) -> Vec3:
    """Component-wise vector subtraction.

    Args:
        a (Vec3): Left vector.
        b (Vec3): Right vector.

    Returns:
        Vec3: Difference vector.
    """
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(v: Vec3, s: float) -> Vec3:
    """Scale vector by scalar.

    Args:
        v (Vec3): Source vector.
        s (float): Scalar multiplier.

    Returns:
        Vec3: Scaled vector.
    """
    return (v[0] * s, v[1] * s, v[2] * s)


def dot(a: Vec3, b: Vec3) -> float:
    """Compute dot product.

    Args:
        a (Vec3): Left vector.
        b (Vec3): Right vector.

    Returns:
        float: Dot product result.
    """
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def length(v: Vec3) -> float:
    """Compute Euclidean vector length.

    Args:
        v (Vec3): Input vector.

    Returns:
        float: Vector magnitude.
    """
    return math.sqrt(dot(v, v))


def normalize(v: Vec3) -> Vec3:
    """Return unit vector or zero vector for zero-length inputs.

    Args:
        v (Vec3): Input vector.

    Returns:
        Vec3: Normalized vector.
    """
    l = length(v)
    if l == 0.0:
        return (0.0, 0.0, 0.0)
    return (v[0] / l, v[1] / l, v[2] / l)


def cross(a: Vec3, b: Vec3) -> Vec3:
    """Compute 3D cross product.

    Args:
        a (Vec3): Left vector.
        b (Vec3): Right vector.

    Returns:
        Vec3: Cross-product vector.
    """
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def clamp(x: float, lo: float, hi: float) -> float:
    """Clamp value into [lo, hi].

    Args:
        x (float): Input value.
        lo (float): Lower bound.
        hi (float): Upper bound.

    Returns:
        float: Clamped value.
    """
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def mix(a: float, b: float, t: float) -> float:
    """Linear interpolation.

    Args:
        a (float): Start value.
        b (float): End value.
        t (float): Blend factor in [0, 1].

    Returns:
        float: Interpolated value.
    """
    return a * (1.0 - t) + b * t


def length2(v: Tuple[float, float]) -> float:
    """Compute 2D Euclidean length.

    Args:
        v (Tuple[float, float]): 2D vector.

    Returns:
        float: Vector magnitude.
    """
    return math.sqrt(v[0] * v[0] + v[1] * v[1])


def length8(v: Tuple[float, float]) -> float:
    """Compute 2D L^8 norm.

    Args:
        v (Tuple[float, float]): 2D vector.

    Returns:
        float: L^8 norm.
    """
    return (abs(v[0]) ** 8.0 + abs(v[1]) ** 8.0) ** (1.0 / 8.0)

