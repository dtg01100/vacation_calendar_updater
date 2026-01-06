from __future__ import annotations

from typing import ClassVar

from PySide6 import QtWidgets


class ThemeManager:
    """Manages Qt application themes using QSS (Qt Style Sheets)."""

    # Predefined themes
    THEMES: ClassVar[dict] = {
        "default": {
            "name": "Default",
            "description": "Clean default theme",
            "style_sheet": """
/* Default Theme - Clean and Professional */
QMainWindow {
    background-color: #f5f5f5;
}

QPushButton {
    background-color: #4CAF50;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #45a049;
}

QPushButton:pressed {
    background-color: #3d8b40;
}

QPushButton:disabled {
    background-color: #cccccc;
    color: #666666;
}

QLineEdit {
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 6px;
    background-color: white;
}

QLineEdit:focus {
    border-color: #4CAF50;
}

QComboBox {
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 6px;
    background-color: white;
    min-width: 150px;
}

QComboBox:focus {
    border-color: #4CAF50;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #ccc;
}

QCheckBox::indicator:checked {
    background-color: #4CAF50;
    border-color: #45a049;
}

QDateEdit {
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 6px;
    background-color: white;
}

QDateEdit:focus {
    border-color: #4CAF50;
}

QTimeEdit {
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 6px;
    background-color: white;
}

QTimeEdit:focus {
    border-color: #4CAF50;
}

QProgressBar {
    border: 1px solid #ddd;
    border-radius: 4px;
    text-align: center;
    background-color: #e0e0e0;
}

QProgressBar::chunk {
    background-color: #4CAF50;
    border-radius: 3px;
}

QStatusBar {
    background-color: #f8f9fa;
    border-top: 1px solid #ddd;
}

QStatusBar::item {
    border: none;
}

QLabel {
    color: #333;
}

QPlainTextEdit {
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: white;
    font-family: 'Consolas', 'Monaco', monospace;
}

QCalendarWidget {
    background-color: white;
    border: 1px solid #ddd;
    border-radius: 4px;
}

QCalendarWidget QToolButton {
    background-color: #f0f0f0;
    border: 1px solid #ddd;
    border-radius: 3px;
    padding: 4px;
}

QCalendarWidget QToolButton:hover {
    background-color: #e0e0e0;
}
""",
        },
        "dark": {
            "name": "Dark",
            "description": "Dark theme for reduced eye strain",
            "style_sheet": """
/* Dark Theme */
QMainWindow {
    background-color: #2b2b2b;
    color: #ffffff;
}

QPushButton {
    background-color: #404040;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #555555;
}

QPushButton:pressed {
    background-color: #303030;
}

QPushButton:disabled {
    background-color: #404040;
    color: #666666;
}

QLineEdit {
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px;
    background-color: #404040;
    color: white;
}

QLineEdit:focus {
    border-color: #4CAF50;
}

QComboBox {
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px;
    background-color: #404040;
    color: white;
    min-width: 150px;
}

QComboBox:focus {
    border-color: #4CAF50;
}

QCheckBox {
    spacing: 8px;
    color: white;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #666;
}

QCheckBox::indicator:checked {
    background-color: #4CAF50;
    border-color: #45a049;
}

QDateEdit {
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px;
    background-color: #404040;
    color: white;
}

QDateEdit:focus {
    border-color: #4CAF50;
}

QTimeEdit {
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px;
    background-color: #404040;
    color: white;
}

QTimeEdit:focus {
    border-color: #4CAF50;
}

QProgressBar {
    border: 1px solid #555555;
    border-radius: 4px;
    text-align: center;
    background-color: #404040;
    color: white;
}

QProgressBar::chunk {
    background-color: #4CAF50;
    border-radius: 3px;
}

QStatusBar {
    background-color: #1e1e1e;
    border-top: 1px solid #404040;
}

QStatusBar::item {
    border: none;
}

QLabel {
    color: #ffffff;
}

QPlainTextEdit {
    border: 1px solid #555555;
    border-radius: 4px;
    background-color: #404040;
    color: white;
    font-family: 'Consolas', 'Monaco', monospace;
}

QCalendarWidget {
    background-color: #404040;
    border: 1px solid #555555;
    border-radius: 4px;
}

QCalendarWidget QToolButton {
    background-color: #303030;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 4px;
}

QCalendarWidget QToolButton:hover {
    background-color: #404040;
}
""",
        },
        "blue": {
            "name": "Ocean Blue",
            "description": "Calming blue theme",
            "style_sheet": """
/* Ocean Blue Theme */
QMainWindow {
    background-color: #e3f2fd;
}

QPushButton {
    background-color: #2196f3;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #1976d2;
}

QPushButton:pressed {
    background-color: #0d47a1;
}

QPushButton:disabled {
    background-color: #90caf9;
    color: #666666;
}

QLineEdit {
    border: 1px solid #1976d2;
    border-radius: 4px;
    padding: 6px;
    background-color: white;
}

QLineEdit:focus {
    border-color: #2196f3;
}

QComboBox {
    border: 1px solid #1976d2;
    border-radius: 4px;
    padding: 6px;
    background-color: white;
    min-width: 150px;
}

QComboBox:focus {
    border-color: #2196f3;
}
""",
        },
    }

    def __init__(self) -> None:
        self.current_theme = "default"
        self.app = None

    def apply_theme(self, app: QtWidgets.QApplication, theme_name: str) -> None:
        """Apply a theme to the application."""
        if theme_name not in self.THEMES:
            raise ValueError(f"Unknown theme: {theme_name}")

        theme = self.THEMES[theme_name]
        self.current_theme = theme_name
        self.app = app
        app.setStyleSheet(theme["style_sheet"])

    def get_current_theme(self) -> str:
        """Get the currently applied theme name."""
        return self.current_theme

    def get_available_themes(self) -> dict[str, dict[str, str]]:
        """Get dictionary of available themes."""
        return {
            name: {"name": theme["name"], "description": theme["description"]}
            for name, theme in self.THEMES.items()
        }

    def set_theme_from_settings(
        self, app: QtWidgets.QApplication, settings_manager
    ) -> None:
        """Set theme based on settings."""
        theme_name = getattr(settings_manager, "get_current_theme", lambda: "default")()
        if theme_name in self.THEMES:
            self.apply_theme(app, theme_name)

    def add_theme_menu_to_menubar(self, menu_bar: QtWidgets.QMenuBar) -> None:
        """Add theme selection menu to menu bar."""
        theme_menu = menu_bar.addMenu("&Theme")
        theme_group = QtWidgets.QActionGroup(self)

        for theme_name, theme_info in self.THEMES.items():
            action = QtWidgets.QAction(theme_info["name"], self)
            action.setCheckable(True)
            action.setData(theme_name)
            action.setToolTip(theme_info["description"])

            if theme_name == self.current_theme:
                action.setChecked(True)

            action.triggered.connect(
                lambda _checked=False, name=theme_name: self._on_theme_changed(name)
            )
            theme_group.addAction(action)
            theme_menu.addAction(action)

    def _on_theme_changed(self, theme_name: str) -> None:
        """Handle theme change from menu selection."""
        if self.app and theme_name != self.current_theme:
            self.apply_theme(self.app, theme_name)

    def create_theme_settings_manager(self) -> ThemeSettingsManager:
        """Create a settings manager for theme preferences."""
        return ThemeSettingsManager()


class ThemeSettingsManager:
    """Settings manager specifically for theme preferences using QSettings."""

    def __init__(self) -> None:
        from PySide6 import QtCore

        self.settings = QtCore.QSettings(
            QtCore.QSettings.Format.IniFormat,
            QtCore.QSettings.Scope.UserScope,
            "VacationCalendarUpdater",
            "Theme",
        )

    def get_current_theme(self) -> str:
        """Get the saved theme preference."""
        return self.settings.value("current_theme", defaultValue="default", type=str)

    def set_current_theme(self, theme_name: str) -> None:
        """Save the theme preference."""
        self.settings.setValue("current_theme", theme_name)
        self.settings.sync()
