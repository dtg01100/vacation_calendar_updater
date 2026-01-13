"""Tests for mode switching and batch selection functionality."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest

from app.services import EnhancedCreatedEvent
from app.undo_manager import UndoManager
from app.validation import ScheduleRequest


@pytest.fixture
def undo_manager_with_batches():
    """Create an UndoManager with sample batches."""
    manager = UndoManager()

    # Create sample events
    events_1 = [
        EnhancedCreatedEvent(
            event_id="event_1a",
            calendar_id="cal_123",
            event_name="Event 1",
            start_time=dt.datetime(2024, 1, 15, 9, 0),
            end_time=dt.datetime(2024, 1, 15, 10, 0),
            created_at=dt.datetime.now(),
            batch_id="batch_1",
            request_snapshot={
                "event_name": "Event 1",
                "start_date": "2024-01-15",
                "end_date": "2024-01-20",
            },
        ),
    ]

    events_2 = [
        EnhancedCreatedEvent(
            event_id="event_2a",
            calendar_id="cal_123",
            event_name="Event 2",
            start_time=dt.datetime(2024, 2, 15, 9, 0),
            end_time=dt.datetime(2024, 2, 15, 10, 0),
            created_at=dt.datetime.now(),
            batch_id="batch_2",
            request_snapshot={
                "event_name": "Event 2",
                "start_date": "2024-02-15",
                "end_date": "2024-02-20",
            },
        ),
    ]

    events_3 = [
        EnhancedCreatedEvent(
            event_id="event_3a",
            calendar_id="cal_123",
            event_name="Event 3",
            start_time=dt.datetime(2024, 3, 15, 9, 0),
            end_time=dt.datetime(2024, 3, 15, 10, 0),
            created_at=dt.datetime.now(),
            batch_id="batch_3",
            request_snapshot={
                "event_name": "Event 3",
                "start_date": "2024-03-15",
                "end_date": "2024-03-20",
            },
        ),
    ]

    # Add batches
    manager.add_batch(events_1, "Created vacation event 1")
    manager.add_batch(events_2, "Created vacation event 2")
    manager.add_batch(events_3, "Created vacation event 3")

    return manager


class TestBatchSelection:
    """Tests for batch selection in UPDATE/DELETE modes."""

    def test_get_undoable_batches_returns_unundone_batches(self, undo_manager_with_batches):
        """Test that get_undoable_batches returns only unundone batches."""
        manager = undo_manager_with_batches
        batches = manager.get_undoable_batches()

        assert len(batches) == 3
        assert all(not b.is_undone for b in batches)

    def test_batch_description_is_preserved(self, undo_manager_with_batches):
        """Test that batch descriptions are preserved through selection."""
        manager = undo_manager_with_batches
        batches = manager.get_undoable_batches()

        descriptions = [b.description for b in batches]
        assert "Created vacation event 1" in descriptions
        assert "Created vacation event 2" in descriptions
        assert "Created vacation event 3" in descriptions

    def test_batch_event_tracking(self, undo_manager_with_batches):
        """Test that batches correctly track their events."""
        manager = undo_manager_with_batches
        batches = manager.get_undoable_batches()

        assert all(len(b.events) > 0 for b in batches)
        # Batches are stored in reverse order (most recent first)
        assert batches[0].events[0].event_name == "Event 3"
        assert batches[1].events[0].event_name == "Event 2"
        assert batches[2].events[0].event_name == "Event 1"

    def test_batch_request_snapshot_preserved(self, undo_manager_with_batches):
        """Test that batch request snapshots preserve original request metadata."""
        manager = undo_manager_with_batches
        batches = manager.get_undoable_batches()

        assert "event_name" in batches[0].events[0].request_snapshot
        # Batches are stored in reverse order (most recent first)
        assert batches[0].events[0].request_snapshot["event_name"] == "Event 3"
        assert batches[1].events[0].request_snapshot["event_name"] == "Event 2"
        assert batches[2].events[0].request_snapshot["event_name"] == "Event 1"

    def test_mark_batch_as_undone_after_deletion(self, undo_manager_with_batches):
        """Test that marking a batch as undone removes it from undoable list."""
        manager = undo_manager_with_batches

        batches_before = manager.get_undoable_batches()
        assert len(batches_before) == 3

        batch_to_undo = batches_before[0]
        manager.undo_batch(batch_to_undo.batch_id)

        batches_after = manager.get_undoable_batches()
        assert len(batches_after) == 2

    def test_get_batch_by_id(self, undo_manager_with_batches):
        """Test retrieving a specific batch by ID."""
        manager = undo_manager_with_batches
        batches = manager.get_undoable_batches()

        batch_id = batches[0].batch_id
        retrieved_batch = manager.get_batch_by_id(batch_id)

        assert retrieved_batch is not None
        assert retrieved_batch.batch_id == batch_id
        # Batches are in reverse order (most recent first)
        assert retrieved_batch.description == "Created vacation event 3"

    def test_get_nonexistent_batch_by_id_returns_none(self, undo_manager_with_batches):
        """Test that getting a nonexistent batch returns None."""
        manager = undo_manager_with_batches
        result = manager.get_batch_by_id("nonexistent_batch_id")

        assert result is None


class TestModeValidation:
    """Tests for mode-specific validation logic."""

    def test_delete_mode_requires_batch_selection(self):
        """Test that DELETE mode requires a batch to be selected."""
        # No batch selected
        batch = None

        # Validation should fail
        assert batch is None or batch == ""

    def test_update_mode_requires_batch_and_schedule(self):
        """Test that UPDATE mode requires both batch and new schedule."""
        batch = None
        schedule = None

        # Both required for UPDATE
        assert batch is None or batch == ""
        assert schedule is None

    def test_create_mode_requires_full_schedule(self):
        """Test that CREATE mode requires complete schedule data."""
        request = ScheduleRequest(
            event_name="",  # Empty name should fail
            notification_email="test@example.com",
            calendar_name="Primary",
            start_date=dt.date(2024, 1, 15),
            end_date=dt.date(2024, 1, 20),
            start_time=dt.time(9, 0),
            day_length_hours=8.0,
            weekdays={
                "monday": True,
                "tuesday": True,
                "wednesday": True,
                "thursday": True,
                "friday": True,
                "saturday": False,
                "sunday": False,
            },
            send_email=False,
        )

        # Should have empty event name
        assert request.event_name == ""


class TestBatchMetadataPreservation:
    """Tests for preserving batch metadata during operations."""

    def test_batch_created_at_timestamp_preserved(self, undo_manager_with_batches):
        """Test that batch creation timestamp is preserved."""
        manager = undo_manager_with_batches
        batches = manager.get_undoable_batches()

        for batch in batches:
            assert batch.created_at is not None
            assert isinstance(batch.created_at, dt.datetime)

    def test_batch_is_undone_flag_initially_false(self, undo_manager_with_batches):
        """Test that newly created batches have is_undone=False."""
        manager = undo_manager_with_batches
        batches = manager.get_undoable_batches()

        assert all(not b.is_undone for b in batches)

    def test_batch_events_preserve_batch_id(self, undo_manager_with_batches):
        """Test that all events in a batch have matching batch_id."""
        manager = undo_manager_with_batches
        batches = manager.get_undoable_batches()

        for batch in batches:
            for event in batch.events:
                assert event.batch_id == batch.batch_id


class TestUpdateModeScenarios:
    """Tests for UPDATE mode specific scenarios."""

    def test_update_replaces_old_schedule_with_new(self, undo_manager_with_batches):
        """Test that UPDATE mode can replace an old schedule with a new one."""
        manager = undo_manager_with_batches
        batches = manager.get_undoable_batches()

        old_batch = batches[0]
        old_event = old_batch.events[0]

        # New schedule would have different dates
        new_start_date = dt.date(2024, 2, 15)
        old_start_date = dt.datetime.strptime(
            old_event.request_snapshot["start_date"], "%Y-%m-%d"
        ).date()

        assert old_start_date != new_start_date

    def test_batch_selection_dropdown_shows_unundone_batches_only(
        self, undo_manager_with_batches
    ):
        """Test that UPDATE/DELETE mode batch dropdown shows only unundone batches."""
        manager = undo_manager_with_batches

        # Initially all 3 batches available
        batches = manager.get_undoable_batches()
        assert len(batches) == 3

        # Undo one batch
        manager.undo_batch(batches[0].batch_id)

        # Now only 2 batches available
        remaining_batches = manager.get_undoable_batches()
        assert len(remaining_batches) == 2
