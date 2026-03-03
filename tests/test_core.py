from pathlib import Path

import pytest

from renderer.app.config import parse_args
from renderer.engine.core import render_image, resolve_worker_count, write_image


def _build_args(output_path: Path, width: int = 10, height: int = 6):
    return parse_args(
        [
            "--quality",
            "draft",
            "--width",
            str(width),
            "--height",
            str(height),
            "--workers",
            "1",
            "--no-progress",
            "--output",
            str(output_path),
        ],
        qt_available=False,
    )


def test_resolve_worker_count() -> None:
    assert resolve_worker_count(3) == 3
    assert resolve_worker_count(0) >= 1


def test_write_image_writes_png_signature(tmp_path: Path) -> None:
    output_path = tmp_path / "io-test.png"
    pixels = bytearray([255, 0, 0, 0, 255, 0])
    write_image(str(output_path), 2, 1, pixels)
    data = output_path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_write_image_rejects_non_png_extension(tmp_path: Path) -> None:
    bad_path = tmp_path / "io-test.jpg"
    with pytest.raises(ValueError, match="Output extension must be .png"):
        write_image(str(bad_path), 2, 1, bytearray([0, 0, 0, 0, 0, 0]))


def test_render_image_smoke(tmp_path: Path) -> None:
    args = _build_args(tmp_path / "render-smoke.png", width=12, height=8)
    pixels = render_image(args, disable_terminal_progress=True)
    assert isinstance(pixels, bytearray)
    assert len(pixels) == args.width * args.height * 3
    assert all(0 <= b <= 255 for b in pixels)
