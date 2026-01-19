"""Dark mode styling utilities for the UI."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16

FONT_SIZE_SMALL = 10
FONT_SIZE_BASE = 11
FONT_SIZE_MEDIUM = 12
FONT_SIZE_LARGE = 14

RADIUS_SM = 2
RADIUS_MD = 3
RADIUS_LG = 4


class DarkModeDetector(QtCore.QObject):
    """Detects system theme changes and emits signals when dark mode status changes."""

    dark_mode_changed = QtCore.Signal(
        bool
    )  # Emits True when dark mode is enabled, False when disabled

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._last_dark_mode_state = is_dark_mode()
        self._app = QtWidgets.QApplication.instance()
        if self._app is not None:
            self._app.paletteChanged.connect(self._on_palette_changed)

    def _on_palette_changed(self, _palette: QtGui.QPalette) -> None:
        """Handle palette change event and check if dark mode status changed."""
        current_state = is_dark_mode()
        if current_state != self._last_dark_mode_state:
            self._last_dark_mode_state = current_state
            self.dark_mode_changed.emit(current_state)


# Create a global detector instance for application-wide use
_detector: DarkModeDetector | None = None


def get_theme_detector() -> DarkModeDetector:
    """Get or create the global theme detector instance."""
    global _detector
    if _detector is None:
        _detector = DarkModeDetector()
    return _detector


def is_dark_mode() -> bool:
    """Check if the system is in dark mode."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return False
    palette = app.palette()
    bg_color = palette.color(QtGui.QPalette.ColorRole.Window)
    return bg_color.lightness() < 128


def get_dark_mode_colors() -> dict[str, str]:
    """Get color scheme for dark mode."""
    return {
        "bg": "#2b2b2b",
        "fg": "#ffffff",
        "panel": "#3c3c3c",
        "border": "#555555",
        "button_bg": "#404040",
        "button_fg": "#ffffff",
        "button_checked": "#0288d1",
        "button_checked_fg": "#ffffff",
        "button_delete_checked": "#d32f2f",
        "button_delete_checked_fg": "#ffffff",
        "error_bg": "#4a1a1a",
        "error_fg": "#ffcccc",
        "info_bg": "#1a3a4a",
        "info_fg": "#cce6ff",
        "success_bg": "#1a4a1a",
        "success_fg": "#ccffcc",
    }


def get_light_mode_colors() -> dict[str, str]:
    """Get color scheme for light mode."""
    return {
        "bg": "#ffffff",
        "fg": "#000000",
        "panel": "#f5f5f5",
        "border": "#e0e0e0",
        "button_bg": "#e0e0e0",
        "button_fg": "#000000",
        "button_checked": "#0288d1",
        "button_checked_fg": "#ffffff",
        "button_delete_checked": "#d32f2f",
        "button_delete_checked_fg": "#ffffff",
        "error_bg": "#fff3e0",
        "error_fg": "#d32f2f",
        "info_bg": "#e1f5fe",
        "info_fg": "#0288d1",
        "success_bg": "#e8f5e9",
        "success_fg": "#2e7d32",
    }


def get_colors() -> dict[str, str]:
    """Get appropriate color scheme based on system theme."""
    if is_dark_mode():
        return get_dark_mode_colors()
    return get_light_mode_colors()


def style_mode_frame(frame: QtWidgets.QFrame) -> None:
    """Style mode selector frame."""
    colors = get_colors()
    frame.setStyleSheet(
        f"background-color: {colors['panel']}; border-bottom: 2px solid {colors['border']};"
    )


def style_mode_button(button: QtWidgets.QPushButton, is_delete: bool = False) -> None:
    """Style a mode button."""
    colors = get_colors()
    checked_color = (
        colors["button_delete_checked"] if is_delete else colors["button_checked"]
    )
    checked_fg = colors["button_delete_checked_fg"]
    unchecked_color = colors["button_bg"]
    unchecked_fg = colors["button_fg"]

    button.setStyleSheet(
        f"QPushButton:checked {{ background-color: {checked_color}; color: {checked_fg}; font-weight: bold; }} "
        f"QPushButton {{ background-color: {unchecked_color}; color: {unchecked_fg}; border-radius: {RADIUS_MD}px; padding: {SPACING_XS}px; }}"
    )


def style_batch_summary_label(label: QtWidgets.QLabel) -> None:
    """Style batch summary label."""
    colors = get_colors()
    label.setStyleSheet(
        f"color: {colors['info_fg']}; font-size: {FONT_SIZE_SMALL}px; font-weight: bold; "
        f"background-color: {colors['info_bg']}; padding: {SPACING_XS}px; border-radius: {RADIUS_MD}px;"
    )


def style_validation_status(label: QtWidgets.QLabel) -> None:
    """Style validation status label."""
    colors = get_colors()
    label.setStyleSheet(
        f"color: {colors['error_fg']}; font-size: {FONT_SIZE_BASE}px; "
        f"background-color: {colors['error_bg']}; padding: {SPACING_XS}px; border-left: {RADIUS_MD}px solid {colors['error_fg']};"
    )


def style_import_panel(frame: QtWidgets.QFrame) -> None:
    """Style import controls panel."""
    colors = get_colors()
    frame.setStyleSheet(
        f"background-color: {colors['panel']}; border: 1px solid {colors['border']}; "
        f"border-radius: {RADIUS_LG}px; padding: {SPACING_SM}px;"
    )


def style_import_button(button: QtWidgets.QPushButton) -> None:
    """Style import action button."""
    colors = get_colors()
    button.setStyleSheet(
        f"QPushButton {{ background-color: {colors['button_checked']}; "
        f"color: {colors['button_checked_fg']}; border-radius: {RADIUS_MD}px; padding: {SPACING_XS}px; }}"
    )


def style_import_list(list_widget: QtWidgets.QListWidget) -> None:
    """Style import event list."""
    colors = get_colors()
    list_widget.setStyleSheet(
        f"""
        QListWidget {{
            background-color: {colors["bg"]};
            color: {colors["fg"]};
            border: 1px solid {colors["border"]};
            border-radius: {RADIUS_MD}px;
            padding: {SPACING_XS}px;
        }}
        QListWidget::item {{
            padding: {SPACING_XS}px;
            border-bottom: 1px solid {colors["border"]};
        }}
        QListWidget::item:selected {{
            background-color: {colors["button_checked"]};
            color: {colors["button_checked_fg"]};
        }}
        """
    )


def style_import_label(label: QtWidgets.QLabel) -> None:
    """Style import status label."""
    colors = get_colors()
    label.setStyleSheet(f"color: {colors['fg']}; font-size: {FONT_SIZE_BASE}px;")


def mark_field_valid(widget: QtWidgets.QWidget) -> None:
    """Mark a form field as valid with a green checkmark indicator."""
    colors = get_colors()
    widget.setStyleSheet(
        f"""
        {widget.__class__.__name__} {{
            background-color: {colors["bg"]};
            color: {colors["fg"]};
            border: 2px solid {colors["success_fg"]};
            border-radius: {RADIUS_SM}px;
            padding: {SPACING_XS}px;
        }}
        """
    )


def mark_field_invalid(widget: QtWidgets.QWidget) -> None:
    """Mark a form field as invalid with a red X indicator."""
    colors = get_colors()
    widget.setStyleSheet(
        f"""
        {widget.__class__.__name__} {{
            background-color: {colors["bg"]};
            color: {colors["fg"]};
            border: 2px solid {colors["error_fg"]};
            border-radius: {RADIUS_SM}px;
            padding: {SPACING_XS}px;
        }}
        """
    )


def clear_field_indicator(widget: QtWidgets.QWidget) -> None:
    """Clear validation indicator from a form field."""
    colors = get_colors()
    widget.setStyleSheet(
        f"""
        {widget.__class__.__name__} {{
            background-color: {colors["bg"]};
            color: {colors["fg"]};
            border: 1px solid {colors["border"]};
            border-radius: {RADIUS_SM}px;
            padding: {SPACING_XS}px;
        }}
        """
    )
