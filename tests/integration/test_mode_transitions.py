"""Integration tests for mode transitions.

Tests transitions between Create, Update, Delete, and Import modes
to ensure proper UI state and data handling during transitions.
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.services import EnhancedCreatedEvent


class TestModeTransitionsCreate:
    """Test transitions involving Create mode."""

    def test_create_to_update_transition(self, mock_api, qtbot):
        """Test transition from Create mode to Update mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        # Switch to create mode first
        window._switch_mode("create")
        assert window.mode == "create"

        # Switch to update mode
        window._switch_mode("update")
        assert window.mode == "update"

    def test_create_to_delete_transition(self, mock_api, qtbot):
        """Test transition from Create mode to Delete mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("create")
        window._switch_mode("delete")
        assert window.mode == "delete"

    def test_create_to_import_transition(self, mock_api, qtbot):
        """Test transition from Create mode to Import mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("create")
        window._switch_mode("import")
        assert window.mode == "import"
        assert window.import_controls_frame.isVisible()


class TestModeTransitionsUpdate:
    """Test transitions involving Update mode."""

    def test_update_to_create_transition(self, mock_api, qtbot):
        """Test transition from Update mode to Create mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("update")
        window._switch_mode("create")
        assert window.mode == "create"

    def test_update_to_delete_transition(self, mock_api, qtbot):
        """Test transition from Update mode to Delete mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("update")
        window._switch_mode("delete")
        assert window.mode == "delete"

    def test_update_to_import_transition(self, mock_api, qtbot):
        """Test transition from Update mode to Import mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("update")
        window._switch_mode("import")
        assert window.mode == "import"


class TestModeTransitionsDelete:
    """Test transitions involving Delete mode."""

    def test_delete_to_create_transition(self, mock_api, qtbot):
        """Test transition from Delete mode to Create mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("delete")
        window._switch_mode("create")
        assert window.mode == "create"

    def test_delete_to_update_transition(self, mock_api, qtbot):
        """Test transition from Delete mode to Update mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("delete")
        window._switch_mode("update")
        assert window.mode == "update"

    def test_delete_to_import_transition(self, mock_api, qtbot):
        """Test transition from Delete mode to Import mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("delete")
        window._switch_mode("import")
        assert window.mode == "import"


class TestModeTransitionsImport:
    """Test transitions involving Import mode."""

    def test_import_to_create_transition(self, mock_api, qtbot):
        """Test transition from Import mode to Create mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("import")
        assert window.import_controls_frame.isVisible()

        window._switch_mode("create")
        assert not window.import_controls_frame.isVisible()
        assert window.mode == "create"

    def test_import_to_update_transition(self, mock_api, qtbot):
        """Test transition from Import mode to Update mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("import")
        window._switch_mode("update")
        assert window.mode == "update"
        assert not window.import_controls_frame.isVisible()

    def test_import_to_delete_transition(self, mock_api, qtbot):
        """Test transition from Import mode to Delete mode."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("import")
        window._switch_mode("delete")
        assert window.mode == "delete"


class TestModeTransitionsAnyToImport:
    """Test any mode to Import transitions."""

    def test_all_modes_have_import_transition(self, mock_api, qtbot):
        """Test that all modes can transition to Import mode."""
        from app.ui.main_window import MainWindow

        modes = ["create", "update", "delete"]

        for mode in modes:
            with pytest.mock.patch("app.ui.main_window.StartupWorker"):
                window = MainWindow(api=mock_api, config=MagicMock())
                qtbot.addWidget(window)

            window._switch_mode(mode)
            window._switch_mode("import")

            assert window.mode == "import"
            assert window.import_controls_frame.isVisible()


class TestModeTransitionState:
    """Test state preservation during mode transitions."""

    def test_import_resets_list_on_entry(self, mock_api, qtbot):
        """Test that switching to import mode resets the list."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        # Add items to import list
        window.import_list.addItem("Old item 1")
        window.import_list.addItem("Old item 2")

        # Switch to import mode
        window._switch_mode("import")

        # List should be cleared
        assert window.import_list.count() == 0

    def test_delete_shows_batch_selector(self, mock_api, qtbot):
        """Test that Delete mode shows batch selector."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("delete")

        # Batch selector should be visible in delete mode
        assert window.batch_selector_btn.isVisible()

    def test_update_shows_batch_selector(self, mock_api, qtbot):
        """Test that Update mode shows batch selector."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("update")

        # Batch selector should be visible in update mode
        assert window.batch_selector_btn.isVisible()

    def test_create_hides_batch_selector(self, mock_api, qtbot):
        """Test that Create mode hides batch selector."""
        from app.ui.main_window import MainWindow

        with pytest.mock.patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=MagicMock())
            qtbot.addWidget(window)

        window._switch_mode("create")

        # Batch selector should not be visible in create mode
        assert not window.batch_selector_btn.isVisible()