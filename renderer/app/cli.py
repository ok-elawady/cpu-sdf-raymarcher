#!/usr/bin/env python3
"""Entrypoint for the CPU SDF ray-marching renderer project."""

import time
from typing import Optional, Sequence

from .config import parse_args
from .gui import has_qt, run_pyside_gui
from ..engine.core import render_image, resolve_worker_count, write_image


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Run GUI mode or CLI render mode based on parsed arguments.

    Args:
        argv (Optional[Sequence[str]]): Optional CLI arguments.

    Returns:
        None: This function does not return a value.
    """
    args = parse_args(argv, qt_available=has_qt())
    if args.gui:
        run_pyside_gui(args)
        return

    start_time = time.perf_counter()
    worker_count = resolve_worker_count(args.workers)
    pixels = render_image(args)
    render_info = f"CPU, {args.aa * args.aa} spp, workers={worker_count}"
    write_image(args.output, args.width, args.height, pixels)
    elapsed = time.perf_counter() - start_time
    print(
        f"Rendered {args.width}x{args.height} to '{args.output}' in {elapsed:.2f} seconds "
        f"({render_info}, quality={args.quality})."
    )


if __name__ == "__main__":
    main()
