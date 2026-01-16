"""Comprehensive tests for multiple batch operations in UndoManager.

Tests focus on critical paths: rapid sequential additions/deletions, bulk operations,
history limit enforcement, mixed undo/redo sequences, and batch interactions.
"""

import datetime as dt
import json

from app.services import EnhancedCreatedEvent
from app.undo_manager import UndoManager


def create_mock_event(
    event_id: str,
    batch_id: str,
    calendar_id: str = "cal1",
    event_name: str = "Test Event",
    days_offset: int = 0,
) -> EnhancedCreatedEvent:
    """Helper to create mock events for testing."""
    start_time = dt.datetime.now() + dt.timedelta(days=days_offset)
    return EnhancedCreatedEvent(
        event_id=event_id,
        calendar_id=calendar_id,
        event_name=event_name,
        start_time=start_time,
        end_time=start_time + dt.timedelta(hours=8),
        created_at=dt.datetime.now(),
        batch_id=batch_id,
        request_snapshot={
            "summary": event_name,
            "start": {"dateTime": start_time.isoformat()},
            "end": {"dateTime": (start_time + dt.timedelta(hours=8)).isoformat()},
        },
    )


class TestRapidSequentialOperations:
    """Test rapid sequential batch additions and deletions."""

    def test_add_10_batches_sequentially(self):
        """Verify adding 10 batches in quick succession works correctly."""
        manager = UndoManager()

        # Add 10 batches rapidly
        for i in range(10):
            batch_id = f"batch_{i}"
            events = [
                create_mock_event(f"event_{i}_1", batch_id, days_offset=i),
                create_mock_event(f"event_{i}_2", batch_id, days_offset=i),
            ]

            manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )

        # Verify all 10 batches are in undo stack
        assert len(manager.undo_stack) == 10

        # Verify correct ordering (most recent first when retrieving)
        undoable = manager.get_undoable_batches()
        assert len(undoable) == 10
        assert undoable[0].description == "Batch 9"
        assert undoable[9].description == "Batch 0"

        # Verify redo stack is empty
        assert len(manager.redo_stack) == 0

    def test_delete_5_batches_sequential_order(self):
        """Test deleting multiple batches in sequential order."""
        manager = UndoManager()

        # Add 10 batches
        operation_ids = []
        for i in range(10):
            batch_id = f"batch_{i}"
            events = [create_mock_event(f"event_{i}", batch_id, days_offset=i)]
            op_id = manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )
            operation_ids.append(op_id)

        # Delete batches 0-4 in sequential order
        for i in range(5):
            # Remove from undo stack
            manager.remove_operation(operation_ids[i])

            # Add delete operation
            events = [create_mock_event(f"event_{i}", f"batch_{i}", days_offset=i)]
            manager.add_operation(
                operation_type="delete",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Delete Batch {i}",
            )

        # Verify remaining batches
        assert len(manager.undo_stack) == 5
        assert len(manager.delete_stack) == 5

        # Verify remaining batches are 5-9
        undoable = manager.get_undoable_batches()
        descriptions = [b.description for b in undoable]
        # Most recent first
        assert descriptions == [f"Batch {i}" for i in range(9, 4, -1)]

    def test_delete_batches_random_order(self):
        """Test deleting batches in non-sequential order."""
        manager = UndoManager()

        # Add 10 batches
        operation_ids = []
        for i in range(10):
            batch_id = f"batch_{i}"
            events = [create_mock_event(f"event_{i}", batch_id)]
            op_id = manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )
            operation_ids.append(op_id)

        # Delete in random order: 7, 2, 9, 1, 5
        delete_order = [7, 2, 9, 1, 5]
        for i in delete_order:
            manager.remove_operation(operation_ids[i])
            events = [create_mock_event(f"event_{i}", f"batch_{i}")]
            manager.add_operation(
                operation_type="delete",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Delete Batch {i}",
            )

        # Verify correct counts
        assert len(manager.undo_stack) == 5
        assert len(manager.delete_stack) == 5

        # Verify remaining batches are 0, 3, 4, 6, 8
        undoable = manager.get_undoable_batches()
        descriptions = set(b.description for b in undoable)
        expected_descriptions = {f"Batch {i}" for i in [0, 3, 4, 6, 8]}
        assert descriptions == expected_descriptions

    def test_undelete_multiple_batches(self):
        """Test undeleting multiple batches in various orders."""
        manager = UndoManager()

        # Create and delete 10 batches
        for i in range(10):
            batch_id = f"batch_{i}"
            events = [create_mock_event(f"event_{i}", batch_id)]

            # Add then delete
            events_to_delete = [create_mock_event(f"event_{i}", f"delete_{i}")]
            manager.add_operation(
                operation_type="delete",
                affected_event_ids=[e.event_id for e in events_to_delete],
                event_snapshots=events_to_delete,
                description=f"Delete Batch {i}",
            )

        # All should be in delete stack
        assert len(manager.delete_stack) == 10
        assert len(manager.undo_stack) == 0

        # Undelete 5 batches by moving them back
        for i in [3, 7, 1, 5, 8]:
            # Find the operation
            delete_op = None
            for op in manager.delete_stack:
                if op.description == f"Delete Batch {i}":
                    delete_op = op
                    break

            if delete_op:
                # Remove from delete stack
                manager.delete_stack.remove(delete_op)

                # Add back as create operation (simulating undelete)
                events = [create_mock_event(f"event_{i}_new", f"undelete_{i}")]
                manager.add_operation(
                    operation_type="create",
                    affected_event_ids=[e.event_id for e in events],
                    event_snapshots=events,
                    description=f"Undelete Batch {i}",
                )

        # Verify counts
        assert len(manager.undo_stack) == 5
        assert len(manager.delete_stack) == 5


class TestHistoryLimits:
    """Test max_history enforcement and trimming behavior."""

    def test_max_history_limit_enforcement(self):
        """Test that history is trimmed when exceeding max_history."""
        manager = UndoManager(max_history=50)

        # Add 60 batches (exceeds 50 limit)
        for i in range(60):
            batch_id = f"batch_{i}"
            events = [create_mock_event(f"event_{i}", batch_id)]
            manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )

        # Should only retain last 50
        assert len(manager.undo_stack) == 50

        # Verify oldest batches were dropped (batch_0 through batch_9)
        descriptions = [op.description for op in manager.undo_stack]
        assert "Batch 0" not in descriptions
        assert "Batch 9" not in descriptions
        assert "Batch 10" in descriptions
        assert "Batch 59" in descriptions

    def test_history_trimming_preserves_recent(self):
        """Verify that trimming preserves the most recent operations."""
        manager = UndoManager(max_history=10)

        # Add 20 batches
        for i in range(20):
            events = [create_mock_event(f"event_{i}", f"batch_{i}")]
            manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )

        # Should have exactly 10
        assert len(manager.undo_stack) == 10

        # Should be batches 10-19 (most recent)
        descriptions = [op.description for op in manager.undo_stack]
        expected_descriptions = [f"Batch {i}" for i in range(10, 20)]
        assert descriptions == expected_descriptions

    def test_delete_stack_respects_max_history(self):
        """Test that delete stack also respects max_history limit."""
        manager = UndoManager(max_history=10)

        # Add 20 delete operations
        for i in range(20):
            events = [create_mock_event(f"event_{i}", f"delete_{i}")]
            manager.add_operation(
                operation_type="delete",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Delete {i}",
            )

        # Should only have 10
        assert len(manager.delete_stack) == 10

        # Should be most recent (delete_10 through delete_19)
        descriptions = [op.description for op in manager.delete_stack]
        expected_descriptions = [f"Delete {i}" for i in range(10, 20)]
        assert descriptions == expected_descriptions

    def test_mixed_operations_both_stacks_trimmed(self):
        """Test trimming when both create and delete operations exceed limit."""
        manager = UndoManager(max_history=20)

        # Add 30 creates
        for i in range(30):
            events = [create_mock_event(f"event_{i}", f"batch_{i}")]
            manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )

        # Add 30 deletes
        for i in range(30):
            events = [create_mock_event(f"event_{i}", f"delete_{i}")]
            manager.add_operation(
                operation_type="delete",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Delete {i}",
            )

        # Both should be trimmed to 20
        assert len(manager.undo_stack) == 20
        assert len(manager.delete_stack) == 20


class TestBatchInteractions:
    """Test interactions between different batch operations."""

    def test_mixed_create_update_delete_sequence(self):
        """Test a realistic sequence of create, update, and delete operations."""
        manager = UndoManager()

        # Create 5 batches
        operation_ids = []
        for i in range(5):
            events = [create_mock_event(f"event_{i}", f"batch_{i}")]
            op_id = manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )
            operation_ids.append(op_id)

        # Update batch 2 (simulated)
        update_events = [create_mock_event("event_2_new", "batch_2_updated")]
        manager.add_operation(
            operation_type="update",
            affected_event_ids=["event_2"],
            event_snapshots=update_events,
            description="Updated Batch 2",
        )

        # Delete batch 3
        manager.remove_operation(operation_ids[3])
        delete_events = [create_mock_event("event_3", "batch_3")]
        manager.add_operation(
            operation_type="delete",
            affected_event_ids=["event_3"],
            event_snapshots=delete_events,
            description="Delete Batch 3",
        )

        # Verify state
        assert len(manager.undo_stack) == 5  # 4 creates + 1 update
        assert len(manager.delete_stack) == 1

        # Verify batch 3 removed from undoable
        undoable = manager.get_undoable_batches()
        descriptions = [b.description for b in undoable]
        assert "Batch 3" not in descriptions
        assert "Updated Batch 2" in descriptions

    def test_undo_multiple_then_create_clears_redo(self):
        """Test that creating after undos clears the redo stack."""
        manager = UndoManager()

        # Create 10 batches
        for i in range(10):
            events = [create_mock_event(f"event_{i}", f"batch_{i}")]
            manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )

        # Undo 5 operations
        for _ in range(5):
            operation = manager.undo()
            assert operation is not None

        # Verify redo stack has 5
        assert len(manager.redo_stack) == 5
        assert len(manager.undo_stack) == 5

        # Create a new batch
        new_events = [create_mock_event("new_event", "new_batch")]
        manager.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in new_events],
            event_snapshots=new_events,
            description="New Batch",
        )

        # Redo stack should be cleared
        assert len(manager.redo_stack) == 0
        assert len(manager.undo_stack) == 6

    def test_undo_redo_multiple_operations(self):
        """Test undo and redo with multiple operations."""
        manager = UndoManager()

        # Create 10 batches
        for i in range(10):
            events = [create_mock_event(f"event_{i}", f"batch_{i}")]
            manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )

        # Undo 5
        for _ in range(5):
            manager.undo()

        assert len(manager.undo_stack) == 5
        assert len(manager.redo_stack) == 5

        # Redo 3
        for _ in range(3):
            manager.redo()

        assert len(manager.undo_stack) == 8
        assert len(manager.redo_stack) == 2

        # Create 2 more (should clear redo)
        for i in range(10, 12):
            events = [create_mock_event(f"event_{i}", f"batch_{i}")]
            manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )

        # Redo should be cleared
        assert len(manager.redo_stack) == 0
        assert len(manager.undo_stack) == 10

    def test_alternating_undo_redo_sequence(self):
        """Test alternating undo/redo operations."""
        manager = UndoManager()

        # Create 5 batches
        for i in range(5):
            events = [create_mock_event(f"event_{i}", f"batch_{i}")]
            manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )

        # Undo 3, redo 2, undo 1
        manager.undo()
        manager.undo()
        manager.undo()
        assert len(manager.undo_stack) == 2
        assert len(manager.redo_stack) == 3

        manager.redo()
        manager.redo()
        assert len(manager.undo_stack) == 4
        assert len(manager.redo_stack) == 1

        manager.undo()
        assert len(manager.undo_stack) == 3
        assert len(manager.redo_stack) == 2


class TestPersistenceWithMultipleBatches:
    """Test save/load with large numbers of operations."""

    def test_save_load_with_30_operations(self, tmp_path):
        """Test persistence with 30 operations in undo stack."""
        manager = UndoManager()

        # Add 30 operations
        for i in range(30):
            events = [create_mock_event(f"event_{i}", f"batch_{i}")]
            manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )

        # Save
        manager.save_history(str(tmp_path))

        # Load into new manager
        manager2 = UndoManager()
        count = manager2.load_history(str(tmp_path))

        assert count == 30
        assert len(manager2.undo_stack) == 30

        # Verify all batches present
        descriptions = [op.description for op in manager2.undo_stack]
        expected_descriptions = [f"Batch {i}" for i in range(30)]
        assert descriptions == expected_descriptions

    def test_save_load_all_four_stacks(self, tmp_path):
        """Test persistence when all four stacks have operations."""
        manager = UndoManager()

        # Add to undo stack
        for i in range(5):
            events = [create_mock_event(f"event_{i}", f"batch_{i}")]
            manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Batch {i}",
            )

        # Undo 2 (creates redo stack)
        manager.undo()
        manager.undo()

        # Add to delete stack
        for i in range(3):
            events = [create_mock_event(f"event_{i}", f"delete_{i}")]
            manager.add_operation(
                operation_type="delete",
                affected_event_ids=[e.event_id for e in events],
                event_snapshots=events,
                description=f"Delete {i}",
            )

        # Undelete one (creates delete_redo stack)
        if manager.delete_stack:
            delete_op = manager.delete_stack[-1]
            manager.delete_stack.remove(delete_op)
            manager.delete_redo_stack.append(delete_op)

        # Verify all stacks populated
        assert len(manager.undo_stack) == 3
        assert len(manager.redo_stack) == 2
        assert len(manager.delete_stack) == 2
        assert len(manager.delete_redo_stack) == 1

        # Save and load
        manager.save_history(str(tmp_path))
        manager2 = UndoManager()
        manager2.load_history(str(tmp_path))

        # Verify all stacks preserved
        assert len(manager2.undo_stack) == 3
        assert len(manager2.redo_stack) == 2
        assert len(manager2.delete_stack) == 2
        assert len(manager2.delete_redo_stack) == 1

    def test_backup_file_creation(self, tmp_path):
        """Test that backup file is created before overwriting."""
        manager = UndoManager()

        # Add and save
        events1 = [create_mock_event("event_1", "batch_1")]
        manager.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in events1],
            event_snapshots=events1,
            description="Batch 1",
        )
        manager.save_history(str(tmp_path))

        # Add more and save again
        events2 = [create_mock_event("event_2", "batch_2")]
        manager.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in events2],
            event_snapshots=events2,
            description="Batch 2",
        )
        manager.save_history(str(tmp_path))

        # Verify backup exists
        backup_path = tmp_path / "undo_history.json.backup"
        assert backup_path.exists()

        # Verify backup contains old data (only 1 operation)
        with open(backup_path) as f:
            backup_data = json.load(f)
        assert len(backup_data["undo_stack"]) == 1

    def test_load_with_corrupted_data(self, tmp_path):
        """Test graceful handling of corrupted JSON data."""
        # Create corrupted file
        history_file = tmp_path / "undo_history.json"
        history_file.write_text("{invalid json content")

        manager = UndoManager()
        count = manager.load_history(str(tmp_path))

        # Should return 0 on failure
        assert count == 0
        assert len(manager.undo_stack) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_batch_operations(self):
        """Test handling of batches with minimal events."""
        manager = UndoManager()

        # Create batch with single event
        events = [create_mock_event("event_1", "batch_1")]
        manager.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in events],
            event_snapshots=events,
            description="Single Event Batch",
        )

        assert len(manager.undo_stack) == 1
        batches = manager.get_undoable_batches()
        assert len(batches) == 1
        assert len(batches[0].events) == 1

    def test_undo_when_stack_empty(self):
        """Test undo returns None when stack is empty."""
        manager = UndoManager()

        result = manager.undo()
        assert result is None

    def test_redo_when_stack_empty(self):
        """Test redo returns None when redo stack is empty."""
        manager = UndoManager()

        # Add and don't undo
        events = [create_mock_event("event_1", "batch_1")]
        manager.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in events],
            event_snapshots=events,
            description="Batch 1",
        )

        # Try to redo (should fail)
        result = manager.redo()
        assert result is None

    def test_remove_nonexistent_operation(self):
        """Test removing operation that doesn't exist."""
        manager = UndoManager()

        # Should not raise exception
        result = manager.remove_operation("nonexistent_op")
        assert result is None
        assert len(manager.undo_stack) == 0

    def test_get_nonexistent_batch(self):
        """Test getting batch that doesn't exist returns None."""
        manager = UndoManager()

        result = manager.get_operation_by_id("nonexistent")
        assert result is None

    def test_signal_emissions(self):
        """Test that signals are emitted correctly during operations."""
        manager = UndoManager()

        history_changed_count = [0]
        operation_created_count = [0]
        redo_cleared_count = [0]

        def on_history_changed():
            history_changed_count[0] += 1

        def on_operation_created(op_id):
            operation_created_count[0] += 1

        def on_redo_cleared():
            redo_cleared_count[0] += 1

        manager.history_changed.connect(on_history_changed)
        manager.operation_created.connect(on_operation_created)
        manager.redo_stack_cleared.connect(on_redo_cleared)

        # Add operation
        events = [create_mock_event("event_1", "batch_1")]
        manager.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in events],
            event_snapshots=events,
            description="Batch 1",
        )

        assert history_changed_count[0] == 1
        assert operation_created_count[0] == 1

        # Undo
        manager.undo()
        assert history_changed_count[0] == 2

        # Add another (should clear redo and emit signal)
        events2 = [create_mock_event("event_2", "batch_2")]
        manager.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in events2],
            event_snapshots=events2,
            description="Batch 2",
        )

        assert redo_cleared_count[0] == 1
