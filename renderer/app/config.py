#!/usr/bin/env python3
"""CLI/default configuration and argument validation helpers."""

import argparse
import sys
from typing import Any, Optional, Protocol, Sequence

from ..common.color_utils import parse_color_literal, rgb_to_hex
from ..common.math_utils import cross, length, normalize, sub
from ..engine.constants import (
    DEFAULT_BOX_COLOR,
    DEFAULT_CAM_POS,
    DEFAULT_CAM_TARGET,
    DEFAULT_CAM_UP,
    DEFAULT_CONE_COLOR,
    DEFAULT_FOV,
    DEFAULT_HEIGHT,
    DEFAULT_OUTPUT,
    DEFAULT_PLANE_COLOR,
    DEFAULT_QUALITY,
    DEFAULT_SPHERE_COLOR,
    DEFAULT_TORUS_COLOR,
    DEFAULT_TUBE_COLOR,
    DEFAULT_WIDTH,
    QUALITY_PRESETS,
)


class ParserLike(Protocol):
    """Minimal parser protocol for shared validation logic."""

    def error(self, message: str) -> Any:
        """Report/raise argument validation error.

        Args:
            message (str): Message value.

        Returns:
            Any: Computed value.
        """
        ...


def apply_quality_defaults(args: argparse.Namespace) -> None:
    """Populate internal renderer knobs from the selected quality preset.

    Args:
        args (argparse.Namespace): Parsed application arguments.

    Returns:
        None: This function does not return a value.
    """
    preset = QUALITY_PRESETS[args.quality]
    args.aa = preset["aa"]
    args.max_steps = preset["max_steps"]
    args.max_dist = preset["max_dist"]
    args.eps = preset["eps"]
    args.shadow_steps = preset["shadow_steps"]
    args.ao_samples = preset["ao_samples"]
    args.preview_every = preset["preview_every"]


def parse_args(
    argv: Optional[Sequence[str]] = None,
    *,
    qt_available: bool = True,
) -> argparse.Namespace:
    """Parse CLI options, derive defaults, and run shared validation.

    Args:
        argv (Optional[Sequence[str]]): Optional CLI arguments.
        qt_available (bool): Qt available value.

    Returns:
        argparse.Namespace: Computed value.
    """
    parser = argparse.ArgumentParser(description="CPU SDF ray-marching renderer.")

    parser.add_argument(
        "--quality",
        choices=tuple(QUALITY_PRESETS.keys()),
        default=DEFAULT_QUALITY,
        help="Quality preset controlling sampling and marching cost.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output image path (.png)")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Image width")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="Image height")
    parser.add_argument("--workers", type=int, default=0, help="Parallel worker processes (0 = auto)")
    parser.add_argument(
        "--cam-pos",
        nargs=3,
        type=float,
        default=DEFAULT_CAM_POS,
        metavar=("X", "Y", "Z"),
        help="Camera position",
    )
    parser.add_argument(
        "--cam-target",
        nargs=3,
        type=float,
        default=DEFAULT_CAM_TARGET,
        metavar=("X", "Y", "Z"),
        help="Camera look-at target",
    )
    parser.add_argument(
        "--cam-up",
        nargs=3,
        type=float,
        default=DEFAULT_CAM_UP,
        metavar=("X", "Y", "Z"),
        help="Camera up vector",
    )
    parser.add_argument("--fov", type=float, default=DEFAULT_FOV, help="Vertical field of view in degrees")
    parser.add_argument(
        "--plane-color",
        default=rgb_to_hex(DEFAULT_PLANE_COLOR),
        help="Plane color (#RRGGBB or R,G,B)",
    )
    parser.add_argument(
        "--sphere-color",
        default=rgb_to_hex(DEFAULT_SPHERE_COLOR),
        help="Sphere color (#RRGGBB or R,G,B)",
    )
    parser.add_argument("--box-color", default=rgb_to_hex(DEFAULT_BOX_COLOR), help="Box color (#RRGGBB or R,G,B)")
    parser.add_argument(
        "--torus-color",
        default=rgb_to_hex(DEFAULT_TORUS_COLOR),
        help="Torus color (#RRGGBB or R,G,B)",
    )
    parser.add_argument(
        "--cone-color",
        default=rgb_to_hex(DEFAULT_CONE_COLOR),
        help="Cone color (#RRGGBB or R,G,B)",
    )
    parser.add_argument(
        "--tube-color",
        default=rgb_to_hex(DEFAULT_TUBE_COLOR),
        help="Tube color (#RRGGBB or R,G,B)",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Run a simple PySide6 GUI with in-window preview (default when no args)",
    )
    parser.add_argument("--no-progress", action="store_true", help="Disable terminal progress output")

    args = parser.parse_args(argv)

    no_cli_args = (argv is None and len(sys.argv) == 1) or (argv is not None and len(argv) == 0)
    if no_cli_args:
        args.gui = True

    color_pairs = [
        ("plane_color", "--plane-color"),
        ("sphere_color", "--sphere-color"),
        ("box_color", "--box-color"),
        ("torus_color", "--torus-color"),
        ("cone_color", "--cone-color"),
        ("tube_color", "--tube-color"),
    ]
    for attr_name, option_name in color_pairs:
        try:
            setattr(args, attr_name, parse_color_literal(getattr(args, attr_name), option_name))
        except ValueError as exc:
            parser.error(str(exc))

    args.torus82_color = args.torus_color
    apply_quality_defaults(args)
    validate_args(args, parser, qt_available=qt_available)
    return args


def validate_args(args: argparse.Namespace, parser: ParserLike, *, qt_available: bool = True) -> None:
    """Centralized argument validation shared by CLI and GUI code paths.

    Args:
        args (argparse.Namespace): Parsed application arguments.
        parser (ParserLike): Parser-like object used to report validation errors.
        qt_available (bool): Qt available value.

    Returns:
        None: This function does not return a value.
    """
    if args.width <= 0:
        parser.error("--width must be greater than 0.")
    if args.height <= 0:
        parser.error("--height must be greater than 0.")
    if args.workers < 0:
        parser.error("--workers must be >= 0.")
    if not (1.0 <= args.fov < 179.0):
        parser.error("--fov must be in range [1, 179).")
    if args.max_steps <= 0:
        parser.error("--max-steps must be greater than 0.")
    if args.gui and not qt_available:
        parser.error("--gui requires PySide6. Install with: pip install PySide6")
    if args.max_dist <= 0.0:
        parser.error("--max-dist must be greater than 0.")
    if args.eps <= 0.0:
        parser.error("--eps must be greater than 0.")
    if args.aa <= 0:
        parser.error("--aa must be greater than 0.")
    if args.preview_every <= 0:
        parser.error("--preview-every must be greater than 0.")
    if args.shadow_steps < 0:
        parser.error("--shadow-steps must be >= 0.")
    if args.ao_samples < 0:
        parser.error("--ao-samples must be >= 0.")

    color_options = [
        ("plane_color", "--plane-color"),
        ("sphere_color", "--sphere-color"),
        ("box_color", "--box-color"),
        ("torus_color", "--torus-color"),
        ("cone_color", "--cone-color"),
        ("tube_color", "--tube-color"),
    ]
    for attr_name, option_name in color_options:
        try:
            rgb = parse_color_literal(getattr(args, attr_name), option_name)
        except ValueError as exc:
            parser.error(str(exc))
        setattr(args, attr_name, rgb)

    cam_pos = tuple(args.cam_pos)
    cam_target = tuple(args.cam_target)
    cam_up = tuple(args.cam_up)

    forward = sub(cam_target, cam_pos)
    if length(forward) == 0.0:
        parser.error("--cam-pos and --cam-target must be different.")
    if length(cam_up) == 0.0:
        parser.error("--cam-up vector must not be zero.")

    view_dir = normalize(forward)
    up_dir = normalize(cam_up)
    right = cross(up_dir, view_dir)
    if length(right) < 1e-8:
        parser.error("--cam-up must not be parallel to viewing direction.")

    out_lower = args.output.lower()
    if not out_lower.endswith(".png"):
        parser.error("--output must end with .png.")
