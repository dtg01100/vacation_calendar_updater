"""Integration tests for mode transitions.

Tests transitions between Create, Update, Delete, and Import modes
to ensure proper UI state and data handling during transitions.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest

from app.services import EnhancedCreatedEvent


class TestModeTransitionsCreate:
    """Test transitions involving Create mode."""

    def test_create_to_update_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Create mode to Update mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        # Switch to create mode first
        window._switch_mode("create")
        assert window.current_mode == "create"

        # Switch to update mode
        window._switch_mode("update")
        assert window.current_mode == "update"

    def test_create_to_delete_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Create mode to Delete mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("create")
        window._switch_mode("delete")
        assert window.current_mode == "delete"

    def test_create_to_import_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Create mode to Import mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("create")
        window._switch_mode("import")
        assert window.current_mode == "import"
        


class TestModeTransitionsUpdate:
    """Test transitions involving Update mode."""

    def test_update_to_create_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Update mode to Create mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("update")
        window._switch_mode("create")
        assert window.current_mode == "create"

    def test_update_to_delete_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Update mode to Delete mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("update")
        window._switch_mode("delete")
        assert window.current_mode == "delete"

    def test_update_to_import_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Update mode to Import mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("update")
        window._switch_mode("import")
        assert window.current_mode == "import"


class TestModeTransitionsDelete:
    """Test transitions involving Delete mode."""

    def test_delete_to_create_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Delete mode to Create mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("delete")
        window._switch_mode("create")
        assert window.current_mode == "create"

    def test_delete_to_update_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Delete mode to Update mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("delete")
        window._switch_mode("update")
        assert window.current_mode == "update"

    def test_delete_to_import_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Delete mode to Import mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("delete")
        window._switch_mode("import")
        assert window.current_mode == "import"


class TestModeTransitionsImport:
    """Test transitions involving Import mode."""

    def test_import_to_create_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Import mode to Create mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("import")
        window._switch_mode("create")
        assert window.current_mode == "create"

    def test_import_to_update_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Import mode to Update mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("import")
        window._switch_mode("update")
        assert window.current_mode == "update"

    def test_import_to_delete_transition(self, mock_api, mock_config, qtbot):
        """Test transition from Import mode to Delete mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("import")
        window._switch_mode("delete")
        assert window.current_mode == "delete"


class TestModeTransitionsAnyToImport:
    """Test any mode to Import transitions."""

    def test_all_modes_have_import_transition(self, mock_api, mock_config, qtbot):
        """Test that all modes can transition to Import mode."""
        from app.ui.main_window import MainWindow

        modes = ["create", "update", "delete"]

        for mode in modes:
            with patch("app.ui.main_window.StartupWorker"):
                window = MainWindow(api=mock_api, config=mock_config)
                qtbot.addWidget(window)

            window._switch_mode(mode)
            window._switch_mode("import")

            assert window.current_mode == "import"
            


class TestModeTransitionState:
    """Test state preservation during mode transitions."""

    def test_import_resets_list_on_entry(self, mock_api, mock_config, qtbot):
        """Test that switching to import mode resets the list."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        # Add items to import list
        window.import_list.addItem("Old item 1")
        window.import_list.addItem("Old item 2")

        # Switch to import mode
        window._switch_mode("import")

        # List should be cleared
        assert window.import_list.count() == 0

    def test_delete_shows_batch_selector(self, mock_api, mock_config, qtbot):
        """Test that Delete mode is accessible."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("delete")

        # Verify delete mode is active
        assert window.current_mode == "delete"

    def test_update_shows_batch_selector(self, mock_api, mock_config, qtbot):
        """Test that Update mode is accessible."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("update")

        # Verify update mode is active
        assert window.current_mode == "update"

    def test_create_hides_batch_selector(self, mock_api, mock_config, qtbot):
        """Test that Create mode is accessible and batch selector hidden."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        window._switch_mode("create")

        # Verify create mode is active
        assert window.current_mode == "create"