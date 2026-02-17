#!/usr/bin/env python3
"""Debug script to test dark mode detection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PySide6 import QtWidgets, QtGui
from app.ui.dark_mode import is_dark_mode, get_colors, get_theme_detector


def main():
    """Test dark mode detection."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    
    print("=== Dark Mode Detection Debug ===")
    print()
    
    # Test 1: Check if app instance exists
    print(f"QApplication instance: {app}")
    print()
    
    # Test 2: Get and print palette information
    palette = app.palette()
    print(f"Palette: {palette}")
    
    # Check various color roles
    window_bg = palette.color(QtGui.QPalette.ColorRole.Window)
    window_text = palette.color(QtGui.QPalette.ColorRole.WindowText)
    base = palette.color(QtGui.QPalette.ColorRole.Base)
    text = palette.color(QtGui.QPalette.ColorRole.Text)
    
    print(f"Window BG: {window_bg.name()} (RGB: {window_bg.red()}, {window_bg.green()}, {window_bg.blue()})")
    print(f"Window Text: {window_text.name()} (RGB: {window_text.red()}, {window_text.green()}, {window_text.blue()})")
    print(f"Base: {base.name()} (RGB: {base.red()}, {base.green()}, {base.blue()})")
    print(f"Text: {text.name()} (RGB: {text.red()}, {text.green()}, {text.blue()})")
    print()
    
    # Test 3: Current dark mode detection
    is_dark = is_dark_mode()
    print(f"is_dark_mode(): {is_dark}")
    print(f"Lightness threshold: 128")
    print(f"Window BG lightness: {window_bg.lightness()}")
    print()
    
    # Test 4: Get colors
    colors = get_colors()
    print(f"Selected colors ({'dark' if is_dark else 'light'} mode):")
    print(f"  Background: {colors['bg']}")
    print(f"  Foreground: {colors['fg']}")
    print(f"  Panel: {colors['panel']}")
    print()
    
    # Test 5: Theme detector
    detector = get_theme_detector()
    print(f"Theme detector instance: {detector}")
    print(f"Signal exists: {hasattr(detector, 'dark_mode_changed')}")
    print()
    
    # Test 6: Force a palette change to see if detector works
    print("--- Testing palette change ---")
    original_palette = app.palette()
    
    # Create a dark palette
    dark_palette = QtGui.QPalette()
    dark_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(30, 30, 30))
    dark_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(255, 255, 255))
    dark_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(45, 45, 45))
    dark_palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(255, 255, 255))
    
    # Signal test function
    def on_theme_changed(is_dark_new: bool):
        print(f"✓ Theme change signal received: Dark mode = {is_dark_new}")
    
    detector.dark_mode_changed.connect(on_theme_changed)
    
    # Change to dark palette
    app.setPalette(dark_palette)
    app.processEvents()
    
    new_is_dark = is_dark_mode()
    print(f"After setting dark palette: is_dark_mode() = {new_is_dark}")
    
    # Restore original palette
    app.setPalette(original_palette)
    app.processEvents()
    
    final_is_dark = is_dark_mode()
    print(f"After restoring original palette: is_dark_mode() = {final_is_dark}")


if __name__ == "__main__":
    main()
