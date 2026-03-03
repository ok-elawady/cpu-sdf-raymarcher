import pytest

from renderer.app.config import parse_args
from renderer.engine.constants import QUALITY_PRESETS


def test_parse_args_minimal_png_configuration() -> None:
    args = parse_args(
        ["--output", "out.png", "--width", "16", "--height", "9", "--no-progress"],
        qt_available=False,
    )
    assert args.output == "out.png"
    assert args.width == 16
    assert args.height == 9
    assert args.gui is False
    assert args.aa == QUALITY_PRESETS["balanced"]["aa"]


def test_parse_args_quality_draft_sets_preset_fields() -> None:
    args = parse_args(["--quality", "draft", "--output", "out.png"], qt_available=False)
    assert args.max_steps == QUALITY_PRESETS["draft"]["max_steps"]
    assert args.shadow_steps == QUALITY_PRESETS["draft"]["shadow_steps"]
    assert args.ao_samples == QUALITY_PRESETS["draft"]["ao_samples"]


def test_parse_args_rejects_non_png_output(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--output", "bad.ppm"], qt_available=False)
    stderr = capsys.readouterr().err
    assert "--output must end with .png." in stderr


def test_parse_args_no_argv_requires_qt_when_defaulting_to_gui(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        parse_args([], qt_available=False)
    stderr = capsys.readouterr().err
    assert "--gui requires PySide6" in stderr
