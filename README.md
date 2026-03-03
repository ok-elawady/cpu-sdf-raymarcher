# CPU SDF Ray-Marching Renderer

This project is a CPU-based ray-marching renderer with a simple PySide6 GUI.

## Project Structure

```text
P2-3/
  cpu_sdf_raymarcher.py   # root launcher
  renderer/               # app package
    __init__.py
    __main__.py
    app/
      __init__.py
      cli.py
      config.py
      gui.py
    engine/
      __init__.py
      constants.py
      core.py
    common/
      __init__.py
      color_utils.py
      math_utils.py
      types.py
  docs/
    images/
      P2-3-GUI.png
      P2-3-output.png
  requirements.txt
  README.md
```

## Requirements

- Python 3.10+ (recommended)
- Dependencies from `requirements.txt`

## Setup

```powershell
pip install -r requirements.txt
```

## Run

Default (opens GUI):

```powershell
python cpu_sdf_raymarcher.py
# or
python -m renderer
```

Command-line render example:

```powershell
python cpu_sdf_raymarcher.py --quality balanced --width 960 --height 540 --output render.png --sphere-color "#FF7755" --box-color "90,170,220"
```

Parallel render example (auto cores):

```powershell
python cpu_sdf_raymarcher.py --quality high --workers 0 --output render-fast.png
```

## CLI Options

```text
--quality {draft,balanced,high}
--output OUTPUT
--width WIDTH
--height HEIGHT
--workers WORKERS
--cam-pos X Y Z
--cam-target X Y Z
--cam-up X Y Z
--fov FOV
--plane-color COLOR
--sphere-color COLOR
--box-color COLOR
--torus-color COLOR
--cone-color COLOR
--tube-color COLOR
--gui
--no-progress
```

Notes:
- Running with no arguments opens the GUI by default.
- In GUI mode, advanced render internals (epsilon, shadow steps, etc.) are set automatically from the selected quality preset.
- `--workers` uses process-based parallelism (`0` = auto core count, `1` = single worker).
- CLI color values accept `#RRGGBB`, `RRGGBB`, `0xRRGGBB`, or `R,G,B`.
- Colors are internally normalized to RGB tuples.
- Wheel sub-shapes share the same `--torus-color` for a simpler interface.
- GUI color rows show both formats for readability: `#RRGGBB (R, G, B)`.


