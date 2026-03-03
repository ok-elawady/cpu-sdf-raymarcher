#!/usr/bin/env python3
"""PySide6 GUI wrapper for configuring and running CPU SDF renders."""

import argparse
import sys
import time
from typing import TYPE_CHECKING, Any, Dict, Tuple, cast

from .config import apply_quality_defaults, validate_args
from ..common.color_utils import rgb_to_hex
from ..engine.constants import (
    DEFAULT_CAM_UP,
    QUALITY_PRESETS,
    RESOLUTION_OPTIONS,
)
from ..engine.core import (
    render_image,
    write_image,
)

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except Exception:
    QtCore = None
    QtGui = None
    QtWidgets = None


QtCoreT = cast(Any, QtCore)
QtGuiT = cast(Any, QtGui)
QtWidgetsT = cast(Any, QtWidgets)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget as _QtWidgetBase
else:
    _QtWidgetBase = QtWidgetsT.QWidget if QtWidgets is not None else object


def has_qt() -> bool:
    """Return True when all required PySide6 modules are importable.

    Args:
        None.

    Returns:
        bool: Computed result.
    """
    return QtWidgets is not None and QtCore is not None and QtGui is not None


class QtRenderWindow(_QtWidgetBase):
    """Single-window Qt UI for setting parameters and previewing render progress."""

    def __init__(self, args: argparse.Namespace) -> None:
        """Build window layout, initialize widgets, and seed control defaults.

        Args:
            args (argparse.Namespace): Parsed application arguments.

        Returns:
            None: This function does not return a value.
        """
        super().__init__()
        self.initial_args = args
        self.current_render_args = args
        self._last_preview_row = -1
        self.color_values: Dict[str, Tuple[int, int, int]] = {}

        self.setWindowTitle("CPU SDF Render Control (PySide6)")
        self.resize(max(980, args.width + 420), max(720, args.height + 180))

        root = QtWidgetsT.QHBoxLayout(self)

        controls_wrap = QtWidgetsT.QScrollArea()
        controls_wrap.setWidgetResizable(True)
        controls_host = QtWidgetsT.QWidget()
        self.controls_layout = QtWidgetsT.QFormLayout(controls_host)
        controls_wrap.setWidget(controls_host)
        controls_wrap.setMinimumWidth(460)
        root.addWidget(controls_wrap, 0)

        preview_panel = QtWidgetsT.QVBoxLayout()
        root.addLayout(preview_panel, 1)

        self.image_label = QtWidgetsT.QLabel()
        self.image_label.setAlignment(QtCoreT.Qt.AlignCenter)
        self.image_label.setMinimumSize(args.width, args.height)
        self.image_label.setStyleSheet("background-color: #1f2329; color: #d0d7de; border: 1px solid #30363d;")
        self.image_label.setText("Set parameters and click Run")
        preview_panel.addWidget(self.image_label, 1)

        self.progress_bar = QtWidgetsT.QProgressBar()
        self.progress_bar.setRange(0, args.height)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p% (%v/%m rows)")
        preview_panel.addWidget(self.progress_bar)

        self.status_label = QtWidgetsT.QLabel("Idle")
        preview_panel.addWidget(self.status_label)

        self.run_button = QtWidgetsT.QPushButton("Run Render")
        self.run_button.clicked.connect(self.start_render)
        preview_panel.addWidget(self.run_button)

        self._build_controls(args)

    def _build_controls(self, args: argparse.Namespace) -> None:
        """Create the visible user inputs.

        Args:
            args (argparse.Namespace): Parsed application arguments.

        Returns:
            None: This function does not return a value.
        """
        self.quality_combo = QtWidgetsT.QComboBox()
        self.quality_combo.addItems(list(QUALITY_PRESETS.keys()))
        self.quality_combo.setCurrentText(str(args.quality))
        self.controls_layout.addRow("Quality", self.quality_combo)

        self.workers_spin = QtWidgetsT.QSpinBox()
        self.workers_spin.setRange(0, 128)
        self.workers_spin.setValue(int(getattr(args, "workers", 0)))
        self.workers_spin.setToolTip("0 uses all available CPU cores.")
        self.controls_layout.addRow("Workers (0=auto)", self.workers_spin)

        self.resolution_combo = QtWidgetsT.QComboBox()
        current = (int(args.width), int(args.height))
        selected_index = -1
        for label, w, h in RESOLUTION_OPTIONS:
            self.resolution_combo.addItem(label, (w, h))
            if (w, h) == current:
                selected_index = self.resolution_combo.count() - 1
        if selected_index < 0:
            custom_label = f"Custom ({current[0]}x{current[1]})"
            self.resolution_combo.addItem(custom_label, current)
            selected_index = self.resolution_combo.count() - 1
        self.resolution_combo.setCurrentIndex(selected_index)
        self.controls_layout.addRow("Resolution", self.resolution_combo)

        self.output_edit = QtWidgetsT.QLineEdit(str(args.output))
        self.controls_layout.addRow("Output", self.output_edit)

        self.preview_check = QtWidgetsT.QCheckBox("Live in-window preview while rendering")
        self.preview_check.setChecked(True)
        self.controls_layout.addRow("", self.preview_check)

        self.fov_spin = QtWidgetsT.QDoubleSpinBox()
        self.fov_spin.setRange(1.0, 179.0)
        self.fov_spin.setDecimals(2)
        self.fov_spin.setValue(float(args.fov))
        self.controls_layout.addRow("FOV", self.fov_spin)

        self.cam_pos_edit = QtWidgetsT.QLineEdit(f"{args.cam_pos[0]}, {args.cam_pos[1]}, {args.cam_pos[2]}")
        self.controls_layout.addRow("Cam Pos (x,y,z)", self.cam_pos_edit)
        self.cam_target_edit = QtWidgetsT.QLineEdit(f"{args.cam_target[0]}, {args.cam_target[1]}, {args.cam_target[2]}")
        self.controls_layout.addRow("Cam Target (x,y,z)", self.cam_target_edit)

        self._add_color_picker_row("plane_color", "Plane Color", tuple(args.plane_color))
        self._add_color_picker_row("sphere_color", "Sphere Color", tuple(args.sphere_color))
        self._add_color_picker_row("box_color", "Box Color", tuple(args.box_color))
        self._add_color_picker_row("torus_color", "Torus Color", tuple(args.torus_color))
        self._add_color_picker_row("cone_color", "Cone Color", tuple(args.cone_color))
        self._add_color_picker_row("tube_color", "Tube Color", tuple(args.tube_color))

    def _add_color_picker_row(self, attr_name: str, label: str, rgb: Tuple[int, int, int]) -> None:
        """Create one row containing a color button and RGB text readout.

        Args:
            attr_name (str): Attr name value.
            label (str): Label value.
            rgb (Tuple[int, int, int]): Rgb value.

        Returns:
            None: This function does not return a value.
        """
        row = QtWidgetsT.QWidget()
        layout = QtWidgetsT.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        button = QtWidgetsT.QPushButton("Pick Color")
        text_label = QtWidgetsT.QLabel()
        self.color_values[attr_name] = rgb
        self._set_color_row_visuals(button, text_label, rgb)
        button.clicked.connect(lambda _, name=attr_name, btn=button, lbl=text_label: self._pick_color(name, btn, lbl))

        layout.addWidget(button, 0)
        layout.addWidget(text_label, 1)
        self.controls_layout.addRow(label, row)

    @staticmethod
    def _set_color_row_visuals(button: Any, label: Any, rgb: Tuple[int, int, int]) -> None:
        """Apply selected RGB to both the swatch button and its text label.

        Args:
            button (Any): Button value.
            label (Any): Label value.
            rgb (Tuple[int, int, int]): Rgb value.

        Returns:
            None: This function does not return a value.
        """
        r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
        label.setText(f"{rgb_to_hex((r, g, b))} ({r}, {g}, {b})")
        button.setStyleSheet(
            "QPushButton {"
            f"background-color: rgb({r}, {g}, {b});"
            "border: 1px solid #777;"
            "padding: 4px 10px;"
            "}"
        )

    def _pick_color(self, attr_name: str, button: Any, label: Any) -> None:
        """Open Qt color picker and update stored/displayed value.

        Args:
            attr_name (str): Attr name value.
            button (Any): Button value.
            label (Any): Label value.

        Returns:
            None: This function does not return a value.
        """
        current = self.color_values[attr_name]
        selected = QtWidgetsT.QColorDialog.getColor(QtGuiT.QColor(*current), self, "Choose color")
        if not selected.isValid():
            return
        rgb = (selected.red(), selected.green(), selected.blue())
        self.color_values[attr_name] = rgb
        self._set_color_row_visuals(button, label, rgb)

    @staticmethod
    def _parse_vec3(text: str, label: str) -> Tuple[float, float, float]:
        """Parse 'x,y,z' text into a numeric tuple with clear validation errors.

        Args:
            text (str): Text value.
            label (str): Label value.

        Returns:
            Tuple[float, float, float]: Tuple containing computed values.
        """
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 3:
            raise ValueError(f"{label} must have exactly 3 comma-separated values.")
        try:
            return float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError as exc:
            raise ValueError(f"{label} values must be numeric.") from exc

    def _build_args_from_controls(self) -> argparse.Namespace:
        """Collect current GUI values into a validated argparse namespace.

        Args:
            None.

        Returns:
            argparse.Namespace: Computed value.
        """
        args = argparse.Namespace(**vars(self.initial_args))

        args.quality = self.quality_combo.currentText()
        args.workers = int(self.workers_spin.value())
        args.output = self.output_edit.text().strip()
        resolution = self.resolution_combo.currentData()
        if resolution is None:
            raise ValueError("Please choose a resolution.")
        args.width, args.height = int(resolution[0]), int(resolution[1])
        args.no_progress = True

        args.fov = float(self.fov_spin.value())
        args.cam_pos = self._parse_vec3(self.cam_pos_edit.text(), "Cam Pos")
        args.cam_target = self._parse_vec3(self.cam_target_edit.text(), "Cam Target")
        args.cam_up = DEFAULT_CAM_UP

        args.plane_color = self.color_values["plane_color"]
        args.sphere_color = self.color_values["sphere_color"]
        args.box_color = self.color_values["box_color"]
        args.torus_color = self.color_values["torus_color"]
        args.torus82_color = args.torus_color
        args.cone_color = self.color_values["cone_color"]
        args.tube_color = self.color_values["tube_color"]

        apply_quality_defaults(args)
        args.gui = True
        return args

    @staticmethod
    def _validate_for_gui(args: argparse.Namespace) -> None:
        """Run shared argument validation and surface errors as ValueError for UI use.

        Args:
            args (argparse.Namespace): Parsed application arguments.

        Returns:
            None: This function does not return a value.
        """

        class _GuiParser:
            """Tiny adapter that mimics argparse parser.error."""

            @staticmethod
            def error(message: str):
                """Raise validation errors as ``ValueError`` for GUI handling.

                Args:
                    message (str): Validation error message.

                Returns:
                    Any: This function always raises an exception.
                """
                raise ValueError(message)

        validate_args(args, _GuiParser(), qt_available=True)

    def _set_preview_from_pixels(self, pixels: bytearray, width: int, height: int) -> None:
        """Push current RGB buffer into QLabel preview.

        Args:
            pixels (bytearray): Pixels input value.
            width (int): Width input value.
            height (int): Height input value.

        Returns:
            None: This function does not return a value.
        """
        image_format = getattr(QtGuiT.QImage, "Format_RGB888", QtGuiT.QImage.Format.Format_RGB888)
        qimg = QtGuiT.QImage(bytes(pixels), width, height, width * 3, image_format)
        self.image_label.setPixmap(QtGuiT.QPixmap.fromImage(qimg))

    def _on_row(self, done_rows: int, pixels: bytearray, start_time: float) -> None:
        """Row callback used by renderer to update progress + live preview.

        Args:
            done_rows (int): Done rows value.
            pixels (bytearray): Pixels input value.
            start_time (float): Start time value.

        Returns:
            None: This function does not return a value.
        """
        total_rows = self.current_render_args.height
        self.progress_bar.setValue(done_rows)
        percent = (100.0 * done_rows) / max(1, total_rows)
        elapsed = time.perf_counter() - start_time
        self.status_label.setText(
            f"Rendering {percent:6.2f}% ({done_rows}/{total_rows} rows, {elapsed:.1f}s)"
        )

        should_update_image = done_rows == total_rows
        if self.preview_check.isChecked():
            should_update_image = (
                should_update_image
                or self._last_preview_row < 0
                or (done_rows - self._last_preview_row) >= int(self.current_render_args.preview_every)
            )
        if should_update_image:
            self._set_preview_from_pixels(pixels, self.current_render_args.width, self.current_render_args.height)
            self._last_preview_row = done_rows

        app = QtWidgetsT.QApplication.instance()
        if app is not None:
            app.processEvents(QtCoreT.QEventLoop.AllEvents, 1)

    def start_render(self) -> None:
        """Validate input, run render, save output, and report status.

        Args:
            None.

        Returns:
            None: This function does not return a value.
        """
        try:
            render_args = self._build_args_from_controls()
            self._validate_for_gui(render_args)
        except Exception as exc:
            self.status_label.setText(f"Invalid parameters: {exc}")
            return

        self.current_render_args = render_args
        self.run_button.setEnabled(False)
        self.progress_bar.setRange(0, render_args.height)
        self.progress_bar.setValue(0)
        self._last_preview_row = -1
        self.image_label.setMinimumSize(render_args.width, render_args.height)
        self.status_label.setText("Starting render...")

        start_time = time.perf_counter()
        try:
            pixels = render_image(
                render_args,
                row_callback=self._on_row,
                disable_terminal_progress=True,
            )
            write_image(render_args.output, render_args.width, render_args.height, pixels)
            elapsed = time.perf_counter() - start_time
            self.status_label.setText(
                f"Done in {elapsed:.2f}s. Saved '{render_args.output}' ({render_args.width}x{render_args.height}, quality={render_args.quality})"
            )
        except Exception as exc:
            self.status_label.setText(f"Render failed: {exc}")
            print(f"Render failed: {exc}", file=sys.stderr)
        finally:
            self.progress_bar.setRange(0, max(1, render_args.height))
            self.run_button.setEnabled(True)


def run_pyside_gui(args: argparse.Namespace) -> int:
    """Launch Qt window (or reuse existing QApplication in embedded contexts).

    Args:
        args (argparse.Namespace): Parsed application arguments.

    Returns:
        int: Computed result.
    """
    if not has_qt():
        raise RuntimeError(
            "PySide6 is not installed. Install with:\n"
            "  pip install PySide6"
        )

    app = QtWidgets.QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QtWidgets.QApplication(sys.argv)

    window = QtRenderWindow(args)
    window.show()

    if owns_app:
        return app.exec()
    return 0
