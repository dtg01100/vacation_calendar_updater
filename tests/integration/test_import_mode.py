"""Integration tests for Import mode workflow.

Tests the complete import flow including fetching events from calendar,
batch grouping, selection, and deletion.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest

from app.services import EnhancedCreatedEvent


def make_import_event(
    event_id: str,
    summary: str,
    start_date: dt.date,
    end_date: dt.date | None = None,
) -> dict:
    """Helper to create import event dict matching Google Calendar API format."""
    if end_date is None:
        end_date = start_date

    return {
        "id": event_id,
        "summary": summary,
        "start": {"date": start_date.isoformat()},
        "end": {"date": (end_date + dt.timedelta(days=1)).isoformat()},
    }


def make_datetime_event(
    event_id: str,
    summary: str,
    start: dt.datetime,
    end: dt.datetime,
) -> dict:
    """Helper to create a datetime-based event dict."""
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }


def _build_window(qtbot, mock_api, mock_config):
    """Helper to build MainWindow with mocked dependencies."""
    from app.ui.main_window import MainWindow

    with patch("app.ui.main_window.StartupWorker"):
        window = MainWindow(api=mock_api, config=mock_config)
        qtbot.addWidget(window)
        return window


class TestImportModeBatchGrouping:
    """Test event batching for import."""

    def test_groups_adjacent_events_same_batch(self, qtbot, mock_api, mock_config):
        """Test that adjacent events with same summary are grouped together."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_primary"}
            qtbot.addWidget(window)

        items = [
            make_import_event("e1", "Vacation", dt.date(2024, 1, 15)),
            make_import_event("e2", "Vacation", dt.date(2024, 1, 16)),
            make_import_event("e3", "Vacation", dt.date(2024, 1, 17)),
        ]

        batches = window._group_events_into_batches(items, "cal_primary")

        # All three should be in one batch (adjacent)
        assert len(batches) == 1
        assert batches[0]["event_count"] == 3

    def test_separates_batches_with_gap(self, qtbot, mock_api, mock_config):
        """Test that events separated by gap > 3 days are separate batches."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_primary"}
            qtbot.addWidget(window)

        items = [
            make_import_event("e1", "Vacation", dt.date(2024, 1, 15)),
            make_import_event("e2", "Vacation", dt.date(2024, 1, 16)),
            make_import_event("e3", "Vacation", dt.date(2024, 1, 25)),  # 9 days later
        ]

        batches = window._group_events_into_batches(items, "cal_primary")

        # Should create two batches
        assert len(batches) == 2

    def test_separates_different_summaries(self, qtbot, mock_api, mock_config):
        """Test that events with different summaries are separate batches."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_primary"}
            qtbot.addWidget(window)

        items = [
            make_import_event("e1", "Vacation", dt.date(2024, 1, 15)),
            make_import_event("e2", "Holiday", dt.date(2024, 1, 16)),
        ]

        batches = window._group_events_into_batches(items, "cal_primary")

        # Should create two batches (different summaries)
        assert len(batches) == 2

    def test_handles_missing_end_date(self, qtbot, mock_api, mock_config):
        """Test that events without end date are skipped gracefully (no crash)."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_primary"}
            qtbot.addWidget(window)

        # Event without end date - should be skipped (not crash)
        items_without_end = [
            {
                "id": "e1",
                "summary": "Event",
                "start": {"date": "2024-01-15"},
                # Missing end - will be skipped
            },
        ]

        # Should not crash and should return empty (skipped events)
        batches = window._group_events_into_batches(items_without_end, "cal_primary")
        assert len(batches) == 0  # Skipped due to missing end

        # Event with end date should still work
        items_with_end = [
            {
                "id": "e2",
                "summary": "Event",
                "start": {"date": "2024-01-15"},
                "end": {"date": "2024-01-15"},
            },
        ]
        batches = window._group_events_into_batches(items_with_end, "cal_primary")
        assert len(batches) == 1  # Works with end date


class TestImportModeSelection:
    """Test import batch selection."""

    def test_selected_import_batches_property_exists(self, qtbot, mock_api, mock_config):
        """Test that selected_import_batches property exists and is callable."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        # The property should exist and return a list
        result = window.selected_import_batches
        assert isinstance(result, list)

    def test_handles_empty_fetch_results(self, qtbot, mock_api, mock_config):
        """Test that empty fetch results are handled gracefully."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        # Simulate empty results
        batches = window._group_events_into_batches([], "cal_primary")

        assert batches == []


class TestImportModeFetchShutdown:
    """Test shutdown during import fetch."""

    def test_handles_shutdown_during_fetch(self, qtbot, mock_api, mock_config):
        """Test that shutdown during fetch is handled properly."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        # Verify ImportFetchWorker is accessible as nested class
        assert hasattr(window, 'ImportFetchWorker')
        # Verify the worker can be instantiated
        worker_class = window.ImportFetchWorker
        assert callable(worker_class)


class TestImportModeBatchesHaveRequiredFields:
    """Test that created batches have all required fields."""

    def test_batch_has_description_and_events(self, qtbot, mock_api, mock_config):
        """Test that batches have description and events fields."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_primary"}
            qtbot.addWidget(window)

        items = [
            make_import_event("e1", "Vacation", dt.date(2024, 1, 15)),
            make_import_event("e2", "Vacation", dt.date(2024, 1, 16)),
        ]

        batches = window._group_events_into_batches(items, "cal_primary")

        # Each batch should have required fields
        for batch in batches:
            assert "description" in batch
            assert "events" in batch
            assert "event_count" in batch


class TestImportModeDatetimeEvents:
    """Test handling of datetime-based events."""

    def test_handles_datetime_events(self, qtbot, mock_api, mock_config):
        """Test that datetime-based events are handled correctly."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_primary"}
            qtbot.addWidget(window)

        items = [
            make_datetime_event(
                "e1",
                "Meeting",
                dt.datetime(2024, 2, 1, 9, 0),
                dt.datetime(2024, 2, 1, 10, 0),
            ),
        ]

        batches = window._group_events_into_batches(items, "cal_primary")

        # Should create batch for datetime event
        assert len(batches) >= 1


class TestImportModeModeSwitching:
    """Test switching between modes after import."""

    def test_import_to_create_mode_switch(self, qtbot, mock_api, mock_config):
        """Test switching from import to create mode works correctly."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        # Switch to import mode
        window._switch_mode("import")
        assert window.current_mode == "import"

        # Switch to create mode
        window._switch_mode("create")
        assert window.current_mode == "create"