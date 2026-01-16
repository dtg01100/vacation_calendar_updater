"""Test for delete and undelete functionality."""
import datetime as dt

import pytest

from app.services import EnhancedCreatedEvent
from app.undo_manager import UndoManager


@pytest.fixture
def undo_manager():
    """Create a fresh UndoManager for each test."""
    return UndoManager()


def create_sample_event(event_id: str, batch_id: str) -> EnhancedCreatedEvent:
    """Create a sample enhanced created event for testing."""
    return EnhancedCreatedEvent(
        event_id=event_id,
        calendar_id="test_calendar",
        event_name=f"Test Event {event_id}",
        start_time=dt.datetime.now(),
        end_time=dt.datetime.now() + dt.timedelta(hours=1),
        created_at=dt.datetime.now(),
        batch_id=batch_id,
        request_snapshot={},
    )


def test_deleted_events_not_in_undoable_list(undo_manager):
    """Test that deleted events do not appear in the undoable batches list."""
    # Create a batch
    batch_id = "batch1"
    events = [create_sample_event("event1", batch_id), create_sample_event("event2", batch_id)]

    # Add as create operation (appears in undoable list)
    undo_manager.add_operation(
        operation_type="create",
        affected_event_ids=[e.event_id for e in events],
        event_snapshots=events,
        description="Test batch",
    )

    # Verify it appears in undoable batches
    undoable = undo_manager.get_undoable_batches()
    assert len(undoable) == 1
    assert undoable[0].batch_id == batch_id

    # Delete the batch (remove from undo_stack and add to delete_stack)
    undo_manager.remove_operation(batch_id)
    undo_manager.add_operation(
        operation_type="delete",
        affected_event_ids=[e.event_id for e in events],
        event_snapshots=events,
        description=f"Deleted: {batch_id}",
    )

    # Verify it no longer appears in undoable batches
    undoable = undo_manager.get_undoable_batches()
    assert len(undoable) == 0

    # Verify it appears in deleted batches
    deleted = undo_manager.get_deleted_batches()
    assert len(deleted) == 1
    assert deleted[0].description == f"Deleted: {batch_id}"


def test_selective_undelete_any_batch_in_any_order(undo_manager):
    """Test that batches can be undeleted in any order, not just LIFO."""
    # Create three batches
    batch1_id = "batch1"
    batch2_id = "batch2"
    batch3_id = "batch3"

    batches = {}
    for batch_id in [batch1_id, batch2_id, batch3_id]:
        events = [create_sample_event(f"event_{batch_id}_1", batch_id)]
        batches[batch_id] = events
        undo_manager.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in events],
            event_snapshots=events,
            description=f"Batch {batch_id}",
        )

    # Verify all three are undoable
    undoable = undo_manager.get_undoable_batches()
    assert len(undoable) == 3

    # Delete all three batches
    for batch_id in [batch1_id, batch2_id, batch3_id]:
        undo_manager.remove_operation(batch_id)
        undo_manager.add_operation(
            operation_type="delete",
            affected_event_ids=[e.event_id for e in batches[batch_id]],
            event_snapshots=batches[batch_id],
            description=f"Deleted: Batch {batch_id}",
        )

    # Verify none appear in undoable, all appear in deleted
    undoable = undo_manager.get_undoable_batches()
    assert len(undoable) == 0

    deleted = undo_manager.get_deleted_batches()
    assert len(deleted) == 3

    # Undelete batch2 first (middle batch, not LIFO)
    batch2_op = None
    for op in undo_manager.delete_stack:
        if "batch2" in op.description:
            batch2_op = op
            break

    assert batch2_op is not None
    undo_manager.delete_stack.remove(batch2_op)
    batch2_op.operation_type = "create"  # Change back to create type when restoring
    undo_manager.undo_stack.append(batch2_op)
    undo_manager.redo_stack.clear()
    undo_manager.delete_redo_stack.clear()

    # Verify batch2 is now undoable, but batch1 and batch3 are still deleted
    undoable = undo_manager.get_undoable_batches()
    undoable_ids = [b.batch_id for b in undoable]
    assert "batch2" in undoable_ids
    assert "batch1" not in undoable_ids
    assert "batch3" not in undoable_ids

    deleted = undo_manager.get_deleted_batches()
    deleted_descs = [b.description for b in deleted]
    assert "Deleted: Batch batch1" in deleted_descs
    assert "Deleted: Batch batch3" in deleted_descs
    assert len(deleted) == 2

    # Undelete batch3 next (last batch)
    batch3_op = None
    for op in undo_manager.delete_stack:
        if "batch3" in op.description:
            batch3_op = op
            break

    assert batch3_op is not None
    undo_manager.delete_stack.remove(batch3_op)
    batch3_op.operation_type = "create"  # Change back to create type when restoring
    undo_manager.undo_stack.append(batch3_op)
    undo_manager.redo_stack.clear()
    undo_manager.delete_redo_stack.clear()

    # Verify batch2 and batch3 are now undoable, but batch1 is still deleted
    undoable = undo_manager.get_undoable_batches()
    undoable_ids = [b.batch_id for b in undoable]
    assert "batch2" in undoable_ids
    assert "batch3" in undoable_ids
    assert "batch1" not in undoable_ids

    deleted = undo_manager.get_deleted_batches()
    deleted_descs = [b.description for b in deleted]
    assert len(deleted) == 1
    assert "Deleted: Batch batch1" in deleted_descs


def test_deleted_batches_properly_ordered(undo_manager):
    """Test that deleted batches are returned in the correct order."""
    # Create and delete three batches in sequence
    import time

    batches = []
    for i in range(1, 4):
        batch_id = f"batch{i}"
        events = [create_sample_event(f"event{i}", batch_id)]
        undo_manager.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in events],
            event_snapshots=events,
            description=f"Batch {i}",
        )
        batches.append((batch_id, events))
        time.sleep(0.01)  # Small delay to ensure different timestamps

    # Delete all batches in order
    for batch_id, events in batches:
        undo_manager.remove_operation(batch_id)
        undo_manager.add_operation(
            operation_type="delete",
            affected_event_ids=[e.event_id for e in events],
            event_snapshots=events,
            description=f"Deleted: Batch {batch_id}",
        )

    # Get deleted batches (should return in order added to delete_stack)
    deleted = undo_manager.get_deleted_batches()
    assert len(deleted) == 3

    # Batches should be in the order they were deleted
    assert "batch1" in deleted[0].description
    assert "batch2" in deleted[1].description
    assert "batch3" in deleted[2].description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
