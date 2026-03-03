#!/usr/bin/env python3
"""Color parsing and conversion helpers."""

from typing import Any

from .math_utils import clamp
from .types import Color, Rgb8


def rgb_to_hex(rgb: Rgb8) -> str:
    """Format RGB tuple as ``#RRGGBB``.

    Args:
        rgb (Rgb8): RGB color in 0..255 space.

    Returns:
        str: Hex color literal.
    """
    return f"#{int(rgb[0]):02X}{int(rgb[1]):02X}{int(rgb[2]):02X}"


def parse_color_literal(value: Any, label: str) -> Rgb8:
    """Parse color literals from tuple/list or string formats.

    Args:
        value (Any): Color value to parse.
        label (str): Option label used in validation messages.

    Returns:
        Rgb8: Parsed RGB tuple in 0..255 space.
    """
    if isinstance(value, (tuple, list)):
        if len(value) != 3:
            raise ValueError(f"{label} must have exactly 3 RGB components.")
        try:
            r, g, b = int(value[0]), int(value[1]), int(value[2])
        except Exception as exc:
            raise ValueError(f"{label} RGB values must be integers.") from exc
        if any(c < 0 or c > 255 for c in (r, g, b)):
            raise ValueError(f"{label} RGB values must be in range 0..255.")
        return (r, g, b)

    if not isinstance(value, str):
        raise ValueError(f"{label} must be RGB tuple/list or color string.")

    text = value.strip()
    if not text:
        raise ValueError(f"{label} cannot be empty.")

    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 3:
            raise ValueError(f"{label} RGB string must be 'R,G,B'.")
        try:
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError as exc:
            raise ValueError(f"{label} RGB values must be integers.") from exc
        if any(c < 0 or c > 255 for c in (r, g, b)):
            raise ValueError(f"{label} RGB values must be in range 0..255.")
        return (r, g, b)

    hex_text = text
    if hex_text.startswith("#"):
        hex_text = hex_text[1:]
    if hex_text.lower().startswith("0x"):
        hex_text = hex_text[2:]
    if len(hex_text) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in hex_text):
        raise ValueError(f"{label} must be #RRGGBB, RRGGBB, 0xRRGGBB, or R,G,B.")
    return (
        int(hex_text[0:2], 16),
        int(hex_text[2:4], 16),
        int(hex_text[4:6], 16),
    )


def to_unit_color(rgb: Rgb8) -> Color:
    """Convert 8-bit RGB tuple into normalized float color.

    Args:
        rgb (Rgb8): RGB values in 0..255 space.

    Returns:
        Color: RGB values in 0..1 space.
    """
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def gamma_correct(c: Color) -> Color:
    """Convert linear color to display-style gamma.

    Args:
        c (Color): Linear RGB color.

    Returns:
        Color: Gamma-corrected RGB color.
    """
    inv_gamma = 1.0 / 2.2
    return (
        clamp(c[0], 0.0, 1.0) ** inv_gamma,
        clamp(c[1], 0.0, 1.0) ** inv_gamma,
        clamp(c[2], 0.0, 1.0) ** inv_gamma,
    )


def color_to_bytes(c: Color) -> Rgb8:
    """Convert normalized RGB [0..1] to 8-bit RGB [0..255].

    Args:
        c (Color): Input normalized color.

    Returns:
        Rgb8: Quantized 8-bit RGB tuple.
    """
    r = int(clamp(c[0], 0.0, 1.0) * 255.0 + 0.5)
    g = int(clamp(c[1], 0.0, 1.0) * 255.0 + 0.5)
    b = int(clamp(c[2], 0.0, 1.0) * 255.0 + 0.5)
    return r, g, b

