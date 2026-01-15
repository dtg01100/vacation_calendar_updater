#!/usr/bin/env python3
"""Verify delete and undelete functionality."""
import datetime as dt
from app.services import EnhancedCreatedEvent
from app.undo_manager import UndoManager


def create_test_event(event_id: str, batch_id: str) -> EnhancedCreatedEvent:
    """Create a test event."""
    return EnhancedCreatedEvent(
        event_id=event_id,
        calendar_id="test_cal",
        event_name=f"Event {event_id}",
        start_time=dt.datetime.now(),
        end_time=dt.datetime.now() + dt.timedelta(hours=1),
        created_at=dt.datetime.now(),
        batch_id=batch_id,
        request_snapshot={},
    )


def test_delete_and_undelete():
    """Test complete delete and undelete workflow."""
    undo_manager = UndoManager()
    
    # Create a batch
    batch_id = "test_batch"
    events = [create_test_event("event1", batch_id), create_test_event("event2", batch_id)]
    
    # Add as operation
    undo_manager.add_operation(
        operation_type="create",
        affected_event_ids=[e.event_id for e in events],
        event_snapshots=events,
        description="Test Batch",
    )
    
    print("✓ Created batch")
    
    # Verify it appears in undoable list
    undoable = undo_manager.get_undoable_batches()
    assert len(undoable) == 1, f"Expected 1 undoable batch, got {len(undoable)}"
    print("✓ Batch appears in undoable list")
    
    # Verify it doesn't appear in deleted list
    deleted = undo_manager.get_deleted_batches()
    assert len(deleted) == 0, f"Expected 0 deleted batches, got {len(deleted)}"
    print("✓ Batch does NOT appear in deleted list")
    
    # Delete the batch
    undo_manager.remove_operation(batch_id)
    undo_manager.add_operation(
        operation_type="delete",
        affected_event_ids=[e.event_id for e in events],
        event_snapshots=events,
        description=f"Deleted: {batch_id}",
    )
    
    print("✓ Deleted batch")
    
    # Verify it doesn't appear in undoable list anymore
    undoable = undo_manager.get_undoable_batches()
    assert len(undoable) == 0, f"Expected 0 undoable batches after delete, got {len(undoable)}"
    print("✓ Batch no longer appears in undoable list")
    
    # Verify it appears in deleted list
    deleted = undo_manager.get_deleted_batches()
    assert len(deleted) == 1, f"Expected 1 deleted batch, got {len(deleted)}"
    print("✓ Batch appears in deleted list")
    
    # Undelete the batch
    operation = undo_manager.delete_stack[0]
    undo_manager.delete_stack.remove(operation)
    operation.operation_type = "create"
    undo_manager.undo_stack.append(operation)
    
    print("✓ Undeleted batch")
    
    # Verify it appears in undoable list again
    undoable = undo_manager.get_undoable_batches()
    assert len(undoable) == 1, f"Expected 1 undoable batch after undelete, got {len(undoable)}"
    print("✓ Batch reappears in undoable list")
    
    # Verify it doesn't appear in deleted list anymore
    deleted = undo_manager.get_deleted_batches()
    assert len(deleted) == 0, f"Expected 0 deleted batches after undelete, got {len(deleted)}"
    print("✓ Batch no longer appears in deleted list")


def test_selective_undelete_order():
    """Test that multiple batches can be undeleted in any order."""
    undo_manager = UndoManager()
    
    # Create three batches
    batch_ids = ["batch1", "batch2", "batch3"]
    for batch_id in batch_ids:
        events = [create_test_event("event1", batch_id)]
        undo_manager.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in events],
            event_snapshots=events,
            description=f"Batch {batch_id}",
        )
    
    print("✓ Created 3 batches")
    
    # Delete all three
    for batch_id in batch_ids:
        undo_manager.remove_operation(batch_id)
        events = [create_test_event("event1", batch_id)]
        undo_manager.add_operation(
            operation_type="delete",
            affected_event_ids=[e.event_id for e in events],
            event_snapshots=events,
            description=f"Deleted: {batch_id}",
        )
    
    print("✓ Deleted 3 batches")
    
    # Undelete batch2 first (middle batch)
    for op in undo_manager.delete_stack:
        if "batch2" in op.description:
            undo_manager.delete_stack.remove(op)
            op.operation_type = "create"
            undo_manager.undo_stack.append(op)
            break
    
    print("✓ Undeleted batch2 (middle batch)")
    
    # Verify correct batches
    undoable = undo_manager.get_undoable_batches()
    deleted = undo_manager.get_deleted_batches()
    
    undoable_ids = [b.batch_id for b in undoable]
    deleted_ids = [d.batch_id for d in deleted]
    
    assert "batch2" in undoable_ids, "batch2 should be undoable"
    assert "batch1" not in undoable_ids, "batch1 should NOT be undoable"
    assert "batch3" not in undoable_ids, "batch3 should NOT be undoable"
    assert len(deleted) == 2, f"Expected 2 deleted batches, got {len(deleted)}"
    
    print("✓ Verified selective undelete: batch2 restored, batch1 & batch3 still deleted")


if __name__ == "__main__":
    print("\nTesting Delete and Undelete Functionality")
    print("=" * 50)
    
    print("\nTest 1: Basic Delete and Undelete")
    print("-" * 50)
    test_delete_and_undelete()
    
    print("\nTest 2: Selective Undelete in Any Order")
    print("-" * 50)
    test_selective_undelete_order()
    
    print("\n" + "=" * 50)
    print("✓ All tests passed!")
