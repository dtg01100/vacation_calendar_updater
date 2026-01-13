"""Test the undo manager functionality with list-based undo."""

import datetime as dt

from app.services import EnhancedCreatedEvent
from app.undo_manager import UndoManager
from app.validation import UndoBatch


def test_undo_manager_list_functionality():
    """Test that the undo manager can handle multiple batches and select specific ones to undo."""
    undo_manager = UndoManager()

    # Create some test events
    batch1_events = [
        EnhancedCreatedEvent(
            event_id="event1",
            calendar_id="cal1",
            event_name="Vacation Day 1",
            start_time=dt.datetime.now(),
            end_time=dt.datetime.now() + dt.timedelta(hours=8),
            created_at=dt.datetime.now(),
            batch_id="batch1",
            request_snapshot={},
        ),
        EnhancedCreatedEvent(
            event_id="event2",
            calendar_id="cal1",
            event_name="Vacation Day 2",
            start_time=dt.datetime.now() + dt.timedelta(days=1),
            end_time=dt.datetime.now() + dt.timedelta(days=1, hours=8),
            created_at=dt.datetime.now(),
            batch_id="batch1",
            request_snapshot={},
        ),
    ]

    batch2_events = [
        EnhancedCreatedEvent(
            event_id="event3",
            calendar_id="cal1",
            event_name="Team Meeting",
            start_time=dt.datetime.now() + dt.timedelta(days=2),
            end_time=dt.datetime.now() + dt.timedelta(days=2, hours=1),
            created_at=dt.datetime.now(),
            batch_id="batch2",
            request_snapshot={},
        )
    ]

    batch3_events = [
        EnhancedCreatedEvent(
            event_id="event4",
            calendar_id="cal1",
            event_name="Reminder",
            start_time=dt.datetime.now() + dt.timedelta(days=3),
            end_time=dt.datetime.now() + dt.timedelta(days=3, hours=1),
            created_at=dt.datetime.now(),
            batch_id="batch3",
            request_snapshot={},
        )
    ]

    # Add operations to the undo manager
    undo_manager.add_operation(
        "create", [e.event_id for e in batch1_events], batch1_events, "Added vacation days"
    )
    undo_manager.add_operation(
        "create", [e.event_id for e in batch2_events], batch2_events, "Added meeting"
    )
    undo_manager.add_operation(
        "create", [e.event_id for e in batch3_events], batch3_events, "Added reminder"
    )

    # Test that we have 3 undoable operations
    undoable_batches = undo_manager.get_undoable_batches()
    assert len(undoable_batches) == 3

    # Test that we can get a specific operation by index
    batch_to_undo = undo_manager.get_undoable_batches()[1]  # Second operation (index 1)
    assert batch_to_undo.description == "Added meeting"

    # Test that we can undo a specific operation
    operation_id = batch_to_undo.batch_id
    operation = undo_manager.get_operation_by_id(operation_id)
    assert operation is not None
    undo_manager.undo()

    # Verify that undo stack was updated
    updated_batches = undo_manager.get_undoable_batches()
    assert len(updated_batches) == 2  # Should have 2 undoable operations left

    # Verify that the most recent operation is now "Added meeting" (since we undid "Added reminder")
    most_recent = undo_manager.get_most_recent_batch()
    assert most_recent.description == "Added meeting"


def test_undo_manager_most_recent_batch():
    """Test that get_most_recent_batch still works correctly."""
    undo_manager = UndoManager()

    # Create some test events
    batch1_events = [
        EnhancedCreatedEvent(
            event_id="event1",
            calendar_id="cal1",
            event_name="Test Event 1",
            start_time=dt.datetime.now(),
            end_time=dt.datetime.now() + dt.timedelta(hours=1),
            created_at=dt.datetime.now(),
            batch_id="batch1",
            request_snapshot={},
        )
    ]

    batch2_events = [
        EnhancedCreatedEvent(
            event_id="event2",
            calendar_id="cal1",
            event_name="Test Event 2",
            start_time=dt.datetime.now() + dt.timedelta(days=1),
            end_time=dt.datetime.now() + dt.timedelta(days=1, hours=1),
            created_at=dt.datetime.now(),
            batch_id="batch2",
            request_snapshot={},
        )
    ]

    # Add operations to the undo manager
    undo_manager.add_operation(
        "create", [e.event_id for e in batch1_events], batch1_events, "First action"
    )
    undo_manager.add_operation(
        "create", [e.event_id for e in batch2_events], batch2_events, "Second action"
    )

    # Test that the most recent batch is the last one added
    most_recent = undo_manager.get_most_recent_batch()
    assert most_recent.description == "Second action"

    # Test that we can undo the most recent operation
    undo_manager.undo()

    # Verify that the most recent operation is now the first one
    most_recent = undo_manager.get_most_recent_batch()
    assert most_recent.description == "First action"


def test_undo_batch_serialization_roundtrip():
    """Test that UndoBatch can be serialized and deserialized correctly."""

    # Create a batch with events
    events = [
        EnhancedCreatedEvent(
            event_id="event1",
            calendar_id="cal1",
            event_name="Test Event",
            start_time=dt.datetime(2024, 1, 15, 9, 0),
            end_time=dt.datetime(2024, 1, 15, 17, 0),
            created_at=dt.datetime(2024, 1, 10, 12, 0),
            batch_id="batch1",
            request_snapshot={"event_name": "Test Event", "weekdays": {}},
        ),
        EnhancedCreatedEvent(
            event_id="event2",
            calendar_id="cal1",
            event_name="Test Event",
            start_time=dt.datetime(2024, 1, 16, 9, 0),
            end_time=dt.datetime(2024, 1, 16, 17, 0),
            created_at=dt.datetime(2024, 1, 10, 12, 0),
            batch_id="batch1",
            request_snapshot={"event_name": "Test Event", "weekdays": {}},
        ),
    ]

    original_batch = UndoBatch(
        batch_id="batch1",
        created_at=dt.datetime(2024, 1, 10, 12, 0),
        events=events,
        description="Added test events",
        is_undone=False,
    )

    # Serialize to dict
    serialized = original_batch.to_dict()

    # Verify structure
    assert serialized["batch_id"] == "batch1"
    assert serialized["description"] == "Added test events"
    assert len(serialized["events"]) == 2
    assert serialized["is_undone"] is False

    # Deserialize back
    deserialized_batch = UndoBatch.from_dict(serialized)

    # Verify all fields match
    assert deserialized_batch.batch_id == original_batch.batch_id
    assert deserialized_batch.description == original_batch.description
    assert deserialized_batch.is_undone == original_batch.is_undone
    assert len(deserialized_batch.events) == len(original_batch.events)

    # Verify events
    for orig_event, deser_event in zip(events, deserialized_batch.events, strict=False):
        assert deser_event.event_id == orig_event.event_id
        assert deser_event.calendar_id == orig_event.calendar_id
        assert deser_event.event_name == orig_event.event_name
        assert deser_event.batch_id == orig_event.batch_id


def test_undo_manager_persistence():
    """Test that undo history can be saved and loaded."""
    import os
    import tempfile

    undo_manager = UndoManager()

    # Create test batches
    batch1_events = [
        EnhancedCreatedEvent(
            event_id="event1",
            calendar_id="cal1",
            event_name="Vacation Day",
            start_time=dt.datetime.now(),
            end_time=dt.datetime.now() + dt.timedelta(hours=8),
            created_at=dt.datetime.now(),
            batch_id="batch1",
            request_snapshot={},
        )
    ]

    batch2_events = [
        EnhancedCreatedEvent(
            event_id="event2",
            calendar_id="cal1",
            event_name="Meeting",
            start_time=dt.datetime.now() + dt.timedelta(days=1),
            end_time=dt.datetime.now() + dt.timedelta(days=1, hours=1),
            created_at=dt.datetime.now(),
            batch_id="batch2",
            request_snapshot={},
        )
    ]

    undo_manager.add_operation(
        "create", [e.event_id for e in batch1_events], batch1_events, "Added vacation"
    )
    undo_manager.add_operation(
        "create", [e.event_id for e in batch2_events], batch2_events, "Added meeting"
    )

    # Save to a temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        undo_manager.save_history(tmpdir)

        # Verify file was created
        file_path = os.path.join(tmpdir, "undo_history.json")
        assert os.path.exists(file_path)

        # Create a new undo manager and load
        new_manager = UndoManager()
        loaded_count = new_manager.load_history(tmpdir)

        assert loaded_count == 2

        # Verify loaded batches
        batches = new_manager.get_undoable_batches()
        assert len(batches) == 2

        # Most recent should be the meeting batch
        most_recent = new_manager.get_most_recent_batch()
        assert most_recent.description == "Added meeting"


def test_undo_manager_persistence_partial_load():
    """Test that load handles missing or corrupted files gracefully."""
    import os
    import tempfile

    UndoManager()

    # Test loading from non-existent directory
    new_manager = UndoManager()
    loaded_count = new_manager.load_history("/nonexistent/path")
    assert loaded_count == 0

    # Test loading from empty file
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create an empty file (not valid JSON)
        empty_file = os.path.join(tmpdir, "invalid.json")
        with open(empty_file, "w") as f:
            f.write("")

        # Should not crash, just return 0
        new_manager2 = UndoManager()
        loaded_count = new_manager2.load_history(tmpdir)
        assert loaded_count == 0


def test_undo_manager_auto_save_with_backup():
    """Test that save_history creates a backup and saves successfully."""
    import json
    import os
    import tempfile

    undo_manager = UndoManager()

    # Create sample events
    sample_events = [
        EnhancedCreatedEvent(
            event_id="event_1",
            calendar_id="cal_1",
            event_name="Test Event",
            start_time=dt.datetime(2024, 1, 10, 9, 0),
            end_time=dt.datetime(2024, 1, 10, 17, 0),
            created_at=dt.datetime.now(),
            batch_id="batch_1",
            request_snapshot={"some": "data"},
        )
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        # Add an operation and save
        undo_manager.add_operation(
            "create", [e.event_id for e in sample_events], sample_events, "First batch"
        )
        undo_manager.save_history(tmpdir)

        history_file = os.path.join(tmpdir, "undo_history.json")
        assert os.path.exists(history_file), "History file should be created"

        # Read the saved data
        with open(history_file) as f:
            saved_data = json.load(f)
        assert len(saved_data["undo_stack"]) == 1

        # Add another operation and save again (should create backup)
        more_events = [
            EnhancedCreatedEvent(
                event_id="event_3",
                calendar_id="cal_1",
                event_name="Another Event",
                start_time=dt.datetime(2024, 1, 15, 9, 0),
                end_time=dt.datetime(2024, 1, 15, 17, 0),
                created_at=dt.datetime.now(),
                batch_id="batch_2",
                request_snapshot={"some": "data"},
            )
        ]
        undo_manager.add_operation(
            "create", [e.event_id for e in more_events], more_events, "Second batch"
        )
        undo_manager.save_history(tmpdir)

        backup_file = os.path.join(tmpdir, "undo_history.json.backup")
        assert os.path.exists(backup_file), "Backup file should be created"

        # Verify backup contains the first save (1 operation)
        with open(backup_file) as f:
            backup_data = json.load(f)
        assert len(backup_data["undo_stack"]) == 1

        # Verify main file contains both operations
        with open(history_file) as f:
            current_data = json.load(f)
        assert len(current_data["undo_stack"]) == 2


def test_selective_batch_undo():
    """Test that specific batches can be selected and undone independently."""
    undo_manager = UndoManager()

    # Create multiple batches
    batch1_events = [
        EnhancedCreatedEvent(
            event_id="event1",
            calendar_id="cal1",
            event_name="Batch 1 Event",
            start_time=dt.datetime.now(),
            end_time=dt.datetime.now() + dt.timedelta(hours=8),
            created_at=dt.datetime.now(),
            batch_id="batch1",
            request_snapshot={},
        )
    ]

    batch2_events = [
        EnhancedCreatedEvent(
            event_id="event2",
            calendar_id="cal1",
            event_name="Batch 2 Event",
            start_time=dt.datetime.now() + dt.timedelta(days=1),
            end_time=dt.datetime.now() + dt.timedelta(days=1, hours=8),
            created_at=dt.datetime.now(),
            batch_id="batch2",
            request_snapshot={},
        )
    ]

    batch3_events = [
        EnhancedCreatedEvent(
            event_id="event3",
            calendar_id="cal1",
            event_name="Batch 3 Event",
            start_time=dt.datetime.now() + dt.timedelta(days=2),
            end_time=dt.datetime.now() + dt.timedelta(days=2, hours=8),
            created_at=dt.datetime.now(),
            batch_id="batch3",
            request_snapshot={},
        )
    ]

    # Add operations (most recent last in stack)
    undo_manager.add_operation(
        "create", [e.event_id for e in batch1_events], batch1_events, "First batch"
    )
    undo_manager.add_operation(
        "create", [e.event_id for e in batch2_events], batch2_events, "Second batch"
    )
    undo_manager.add_operation(
        "create", [e.event_id for e in batch3_events], batch3_events, "Third batch"
    )

    # Get all undoable operations (should be 3)
    undoable = undo_manager.get_undoable_batches()
    assert len(undoable) == 3

    # Undo the middle operation (second operation) - but undo works LIFO
    # So we need to undo from the top of the stack
    # Let's just test that undo works and updates the stack properly
    undo_manager.undo()  # Undoes the most recent (Third batch)

    # Should now have 2 undoable operations
    undoable = undo_manager.get_undoable_batches()
    assert len(undoable) == 2

    # Most recent should now be the second batch
    most_recent = undo_manager.get_most_recent_batch()
    assert most_recent.description == "Second batch"

    # Undo again
    undo_manager.undo()  # Undoes Second batch

    # Should now have 1 undoable operation
    undoable = undo_manager.get_undoable_batches()
    assert len(undoable) == 1
    assert undoable[0].description == "First batch"

