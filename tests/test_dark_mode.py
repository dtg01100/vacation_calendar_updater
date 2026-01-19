"""Tests for dark mode styling functionality."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ui.dark_mode import (
    DarkModeDetector,
    get_colors,
    get_dark_mode_colors,
    get_light_mode_colors,
    get_theme_detector,
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


def test_theme_detector():
    """Test theme detector singleton and functionality."""
    from PySide6 import QtWidgets
    
    # Create a dummy app for testing
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    
    # Test singleton behavior
    detector1 = get_theme_detector()
    detector2 = get_theme_detector()
    assert detector1 is detector2
    
    # Test detector is an instance of DarkModeDetector
    assert isinstance(detector1, DarkModeDetector)
    
    # Test signal exists
    assert hasattr(detector1, 'dark_mode_changed')


def test_theme_detector_signal():
    """Test that theme detector emits signal when dark mode changes."""
    from PySide6 import QtWidgets, QtGui
    
    # Create a dummy app for testing
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    
    detector = get_theme_detector()
    
    # Track if signal was emitted
    signal_received = False
    
    def on_theme_changed(is_dark: bool):
        nonlocal signal_received
        signal_received = True
    
    detector.dark_mode_changed.connect(on_theme_changed)
    
    # Change palette to trigger detection
    original_palette = app.palette()
    dark_palette = QtGui.QPalette()
    dark_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(30, 30, 30))
    app.setPalette(dark_palette)
    
    # Process events to allow signal to be emitted
    app.processEvents()
    
    # Restore original palette
    app.setPalette(original_palette)
    app.processEvents()
    
    # Verify signal was received
    assert signal_received


if __name__ == "__main__":
    test_dark_mode_detection()
    test_color_schemes()
    test_style_functions()
    test_import_styles()
    test_theme_detector()
    test_theme_detector_signal()