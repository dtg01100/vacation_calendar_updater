"""Tests for dark mode styling functionality."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ui.dark_mode import (
    get_colors,
    get_dark_mode_colors,
    get_light_mode_colors,
    is_dark_mode,
    style_batch_summary_label,
    style_import_button,
    style_import_label,
    style_import_list,
    style_import_panel,
    style_mode_button,
    style_mode_frame,
    style_validation_status,
)


def test_dark_mode_detection():
    """Test dark mode detection."""
    # This will return False in most environments, but the function should work
    result = is_dark_mode()
    assert isinstance(result, bool)


def test_color_schemes():
    """Test color scheme generation."""
    dark_colors = get_dark_mode_colors()
    light_colors = get_light_mode_colors()
    auto_colors = get_colors()

    # Check dark mode colors
    assert dark_colors["bg"] == "#2b2b2b"
    assert dark_colors["fg"] == "#ffffff"
    assert dark_colors["button_checked"] == "#0288d1"

    # Check light mode colors
    assert light_colors["bg"] == "#ffffff"
    assert light_colors["fg"] == "#000000"
    assert light_colors["button_checked"] == "#0288d1"

    # Check auto colors (should match light mode in light environment)
    assert auto_colors["bg"] == "#ffffff"
    assert auto_colors["fg"] == "#000000"


def test_style_functions():
    """Test that style functions exist and can be called."""
    from PySide6 import QtWidgets

    # Create a dummy app for testing
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    # Test style functions (they should not crash)
    frame = QtWidgets.QFrame()
    style_mode_frame(frame)

    button = QtWidgets.QPushButton("Test")
    style_mode_button(button)
    style_mode_button(button, is_delete=True)

    label = QtWidgets.QLabel("Test")
    style_batch_summary_label(label)
    style_validation_status(label)
    style_import_label(label)

    import_frame = QtWidgets.QFrame()
    style_import_panel(import_frame)

    import_button = QtWidgets.QPushButton("Test")
    style_import_button(import_button)

    import_list = QtWidgets.QListWidget()
    style_import_list(import_list)


def test_import_styles():
    """Test import-specific styling."""
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    # Test import panel styling
    import_frame = QtWidgets.QFrame()
    style_import_panel(import_frame)

    # Test import button styling
    import_button = QtWidgets.QPushButton("Fetch")
    style_import_button(import_button)

    # Test import list styling
    import_list = QtWidgets.QListWidget()
    style_import_list(import_list)

    # Test import label styling
    import_label = QtWidgets.QLabel("Status")
    style_import_label(import_label)


if __name__ == "__main__":
    test_dark_mode_detection()
    test_color_schemes()
    test_style_functions()
    test_import_styles()