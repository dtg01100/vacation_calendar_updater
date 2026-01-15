"""Tests for batch selector functionality in UndoManager."""
from __future__ import annotations

import datetime as dt

import pytest

from app.services import EnhancedCreatedEvent
from app.undo_manager import UndoManager
from app.validation import UndoOperation


def create_test_operation(
    batch_id: str = "batch_001",
    *,
    created_at: dt.datetime | None = None,
    event_count: int = 1,
    start_offset_days: int = 0,
    operation_type: str = "create",
) -> UndoOperation:
    """Helper to create test operations with predictable IDs."""
    if created_at is None:
        created_at = dt.datetime.now()

    events = []
    base_date = dt.date.today() + dt.timedelta(days=start_offset_days)

    for i in range(event_count):
        event = EnhancedCreatedEvent(
            event_id=f"event_{batch_id}_{i}",
            event_name=f"Test Event {i}",
            start_time=dt.datetime.combine(base_date, dt.time(9, 0)) + dt.timedelta(days=i),
            end_time=dt.datetime.combine(base_date, dt.time(17, 0)) + dt.timedelta(days=i),
            calendar_id="cal_001",
            created_at=created_at,
            batch_id=batch_id,
            request_snapshot={},
        )
        events.append(event)

    return UndoOperation(
        operation_id=batch_id,
        operation_type=operation_type,
        affected_event_ids=[e.event_id for e in events],
        event_snapshots=events,
        created_at=created_at,
        description=f"Batch {batch_id}",
    )


@pytest.fixture
def undo_manager():
    """Create an UndoManager instance for testing."""
    return UndoManager(parent=None)


class TestGetBatchesForDate:
    """Test cases for UndoManager.get_batches_for_date() method."""
    
    def test_get_batches_for_date_basic(self, undo_manager):
        """Test get_batches_for_date method with basic query."""
        today = dt.date.today()
        
        batch_today = create_test_operation(batch_id="today", start_offset_days=0)
        batch_tomorrow = create_test_operation(batch_id="tomorrow", start_offset_days=1)
        batch_far = create_test_operation(batch_id="far", start_offset_days=15)
        
        undo_manager.undo_stack.append(batch_today)
        undo_manager.undo_stack.append(batch_tomorrow)
        undo_manager.undo_stack.append(batch_far)
        
        # Query for today (±7 days default)
        batches = undo_manager.get_batches_for_date(today, day_range=7)
        batch_ids = [b.batch_id for b in batches]
        
        assert "today" in batch_ids
        assert "tomorrow" in batch_ids
        assert "far" not in batch_ids
    
    def test_get_batches_for_date_boundary(self, undo_manager):
        """Test batches at the exact ±7 day boundary."""
        today = dt.date.today()
        
        batch_7_days_ago = create_test_operation(batch_id="7_ago", start_offset_days=-7)
        batch_7_days_future = create_test_operation(batch_id="7_future", start_offset_days=7)
        batch_8_days_ago = create_test_operation(batch_id="8_ago", start_offset_days=-8)
        
        undo_manager.undo_stack.append(batch_7_days_ago)
        undo_manager.undo_stack.append(batch_7_days_future)
        undo_manager.undo_stack.append(batch_8_days_ago)
        
        batches = undo_manager.get_batches_for_date(today, day_range=7)
        batch_ids = [b.batch_id for b in batches]
        
        assert "7_ago" in batch_ids
        assert "7_future" in batch_ids
        assert "8_ago" not in batch_ids
    
    def test_get_batches_for_date_empty(self, undo_manager):
        """Test with no matching batches."""
        today = dt.date.today()
        batch_far = create_test_operation(batch_id="far", start_offset_days=15)
        undo_manager.undo_stack.append(batch_far)
        
        batches = undo_manager.get_batches_for_date(today, day_range=7)
        assert len(batches) == 0
    
    def test_get_batches_for_date_multiple_events(self, undo_manager):
        """Test batch with multiple events."""
        today = dt.date.today()
        batch = create_test_operation(batch_id="multi", event_count=3, start_offset_days=0)
        undo_manager.undo_stack.append(batch)
        
        batches = undo_manager.get_batches_for_date(today, day_range=7)
        assert len(batches) == 1
        assert len(batches[0].events) == 3
    
    def test_get_batches_for_date_excludes_undone(self, undo_manager):
        """Test that undone batches are excluded."""
        today = dt.date.today()
        batch_active = create_test_operation(batch_id="active", start_offset_days=0)
        batch_deleted = create_test_operation(batch_id="deleted", start_offset_days=0, operation_type="delete")

        # Simulate old history containing a delete op in the main stack; it should be filtered out
        undo_manager.undo_stack.append(batch_active)
        undo_manager.undo_stack.append(batch_deleted)
        
        batches = undo_manager.get_batches_for_date(today, day_range=7)
        batch_ids = [b.batch_id for b in batches]
        
        assert "active" in batch_ids
        assert "deleted" not in batch_ids
    
    def test_get_batches_for_date_custom_range(self, undo_manager):
        """Test with custom day_range."""
        today = dt.date.today()
        batch_3_days = create_test_operation(batch_id="3_days", start_offset_days=3)
        batch_5_days = create_test_operation(batch_id="5_days", start_offset_days=5)
        
        undo_manager.undo_stack.append(batch_3_days)
        undo_manager.undo_stack.append(batch_5_days)
        
        # With range of 3 days
        batches = undo_manager.get_batches_for_date(today, day_range=3)
        batch_ids = [b.batch_id for b in batches]
        
        assert "3_days" in batch_ids
        assert "5_days" not in batch_ids
    
    def test_get_batches_for_date_preserves_order(self, undo_manager):
        """Test that batches are returned in correct order."""
        today = dt.date.today()
        batch1 = create_test_operation(
            batch_id="batch1",
            start_offset_days=0,
            created_at=dt.datetime(2025, 1, 15, 10, 0, 0)
        )
        batch2 = create_test_operation(
            batch_id="batch2",
            start_offset_days=1,
            created_at=dt.datetime(2025, 1, 20, 10, 0, 0)
        )
        
        undo_manager.undo_stack.append(batch1)
        undo_manager.undo_stack.append(batch2)
        
        batches = undo_manager.get_batches_for_date(today, day_range=7)
        batch_ids = [b.batch_id for b in batches]
        
        # Should return in stack order (most recent first)
        assert batch_ids[0] == "batch2"
        assert batch_ids[1] == "batch1"
    
    def test_get_batches_for_date_no_duplicates(self, undo_manager):
        """Test that same batch isn't returned multiple times."""
        today = dt.date.today()
        
        # Single batch with multiple events spanning different days
        batch = create_test_operation(
            batch_id="multi_event",
            event_count=5,
            start_offset_days=0
        )
        undo_manager.undo_stack.append(batch)
        
        batches = undo_manager.get_batches_for_date(today, day_range=7)
        assert len(batches) == 1  # Should only get one batch, not duplicates
    
    def test_get_batches_for_date_ignores_delete_stack(self, undo_manager):
        """Ensure delete stack operations are hidden from date queries."""
        today = dt.date.today()

        batch_visible = create_test_operation(batch_id="visible", start_offset_days=0)
        batch_deleted = create_test_operation(batch_id="deleted", start_offset_days=0, operation_type="delete")

        undo_manager.undo_stack.append(batch_visible)
        undo_manager.delete_stack.append(batch_deleted)

        batches = undo_manager.get_batches_for_date(today, day_range=7)
        batch_ids = [b.batch_id for b in batches]

        assert "visible" in batch_ids
        assert "deleted" not in batch_ids
