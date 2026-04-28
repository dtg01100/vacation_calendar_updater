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
        """Test that events without end date are handled gracefully."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_primary"}
            qtbot.addWidget(window)

        items = [
            {
                "id": "e1",
                "summary": "Event",
                "start": {"date": "2024-01-15"},
                # Missing end
            },
        ]

        batches = window._group_events_into_batches(items, "cal_primary")

        # Should not crash, batch should be created
        assert len(batches) >= 1


class TestImportModeSelection:
    """Test import batch selection."""

    def test_selected_import_batches_returns_checked(self, qtbot, mock_api, mock_config):
        """Test that only checked batches are returned for deletion."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        # Create mock batches
        event1 = EnhancedCreatedEvent(
            event_id="e1",
            calendar_id="cal_primary",
            event_name="Batch 1 Event",
            start_time=dt.datetime(2024, 1, 15, 9, 0),
            end_time=dt.datetime(2024, 1, 15, 17, 0),
            created_at=dt.datetime.now(),
            batch_id="batch1",
            request_snapshot=None,
        )
        event2 = EnhancedCreatedEvent(
            event_id="e2",
            calendar_id="cal_primary",
            event_name="Batch 2 Event",
            start_time=dt.datetime(2024, 1, 25, 9, 0),
            end_time=dt.datetime(2024, 1, 25, 17, 0),
            created_at=dt.datetime.now(),
            batch_id="batch2",
            request_snapshot=None,
        )

        window.import_batches = [
            {"description": "Batch 1", "events": [event1], "event_count": 1},
            {"description": "Batch 2", "events": [event2], "event_count": 1},
        ]

        # Check first batch
        from PySide6 import QtCore, QtWidgets
        for i in range(window.import_list.count()):
            item = window.import_list.item(i)
            if i == 0:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)

        selected = window._get_selected_import_batches()

        # Only first batch should be selected
        assert len(selected) == 1
        assert selected[0]["description"] == "Batch 1"


class TestImportModeEmptyResults:
    """Test import with no new events."""

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

    def test_handles_shutdown_during_fetch(self, mock_api):
        """Test that shutdown during fetch is handled properly."""
        from app.workers import ImportFetchWorker

        # Create worker that will be stopped
        worker = ImportFetchWorker(
            mock_api,
            "cal_primary",
            dt.date(2024, 1, 1),
            dt.date(2024, 12, 31),
            [],
            50,
        )

        # Request stop before starting
        worker.request_stop()

        results = []
        worker.finished.connect(lambda events: results.extend(events))
        worker.run()

        # Should not produce any events
        assert len(results) == 0


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
        """Test switching from import to create mode."""
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)

        # Switch to import mode
        window._switch_mode("import")
        assert window.import_controls_frame.isVisible()

        # Switch to create mode
        window._switch_mode("create")
        assert not window.import_controls_frame.isVisible()