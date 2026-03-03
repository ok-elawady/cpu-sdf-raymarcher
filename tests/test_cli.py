from pathlib import Path

from cpu_sdf_raymarcher.app.cli import main


def test_cli_main_renders_png_and_prints_summary(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "cli-render.png"
    main(
        [
            "--quality",
            "draft",
            "--width",
            "12",
            "--height",
            "8",
            "--workers",
            "1",
            "--no-progress",
            "--output",
            str(output_path),
        ]
    )

    assert output_path.exists()
    stdout = capsys.readouterr().out
    assert "Rendered 12x8" in stdout
    assert str(output_path) in stdout
