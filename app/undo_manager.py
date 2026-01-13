from __future__ import annotations

import contextlib
import datetime as dt
import json
import shutil
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .services import EnhancedCreatedEvent
from .validation import UndoBatch, UndoOperation


class UndoManager(QObject):
    """Manages undo/redo history with dual-stack architecture."""

    # Existing signals (kept for backwards compatibility)
    history_changed = Signal()
    batch_undone = Signal(str)  # batch_id (deprecated)
    events_undone = Signal(str, list)  # batch_id, event_ids (deprecated)
    save_failed = Signal(str)  # error_message

    # New signals for operation-based undo/redo
    operation_created = Signal(str)  # operation_id
    operation_undone = Signal(str)  # operation_id
    operation_redone = Signal(str)  # operation_id
    redo_stack_cleared = Signal()  # no parameters

    def __init__(self, max_history: int = 50, parent=None):
        super().__init__(parent)
        # New dual-stack model
        self.undo_stack: list[UndoOperation] = []
        self.redo_stack: list[UndoOperation] = []
        # Legacy field for backwards compatibility
        self.undo_history: list[UndoBatch] = []
        self.max_history = max_history
        self.persistence_file = "undo_history.json"

    def save_history(self, directory: str | None = None) -> None:
        """Save undo history to a JSON file (v2 schema with dual stacks + v1 backwards compat).

        Args:
            directory: Directory to save the file in (defaults to current directory)
        """
        if directory:
            file_path = Path(directory) / self.persistence_file
        else:
            file_path = Path(self.persistence_file)

        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create backup of existing file before overwriting
        if file_path.exists():
            backup_path = file_path.with_suffix(".json.backup")
            with contextlib.suppress(OSError):
                # Continue even if backup fails - better to save without backup
                shutil.copy(file_path, backup_path)

        # Save v2 format (preferred), but include v1 batches for backwards compat
        data = {
            "version": 2,
            "max_history": self.max_history,
            "undo_stack": [operation.to_dict() for operation in self.undo_stack],
            "redo_stack": [operation.to_dict() for operation in self.redo_stack],
            # Also save v1 batches for backwards compatibility
            "batches": [batch.to_dict() for batch in self.undo_history],
        }

        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            # Log error and emit signal for user notification
            error_msg = f"Failed to save undo history: {e}"
            self.save_failed.emit(error_msg)

    def load_history(self, directory: str | None = None) -> int:
        """Load undo history from a JSON file (supports v1 and v2 schemas).

        Args:
            directory: Directory to load the file from (defaults to current directory)

        Returns:
            Number of operations loaded
        """
        if directory:
            file_path = Path(directory) / self.persistence_file
        else:
            file_path = Path(self.persistence_file)

        if not file_path.exists():
            return 0

        try:
            with open(file_path) as f:
                data = json.load(f)

            version = data.get("version", 1)

            # Clear existing stacks
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.undo_history.clear()

            if version == 1:
                # Migrate v1 to v2
                self._migrate_v1_to_v2(data)
            elif version == 2:
                # Load v2 format directly
                for op_data in data.get("undo_stack", []):
                    try:
                        operation = UndoOperation.from_dict(op_data)
                        self.undo_stack.append(operation)
                    except (KeyError, ValueError):
                        continue

                for op_data in data.get("redo_stack", []):
                    try:
                        operation = UndoOperation.from_dict(op_data)
                        self.redo_stack.append(operation)
                    except (KeyError, ValueError):
                        continue
                
                # Also load legacy v1 batches if present (for backwards compat)
                for batch_data in data.get("batches", []):
                    try:
                        batch = UndoBatch.from_dict(batch_data)
                        self.undo_history.append(batch)
                    except (KeyError, ValueError):
                        continue
            else:
                # Unknown version - return 0 (no history loaded)
                return 0

            # Restore max_history setting
            if "max_history" in data:
                self.max_history = data["max_history"]

            # Trim history if needed
            if len(self.undo_stack) > self.max_history:
                self.undo_stack = self.undo_stack[-self.max_history :]

            self.history_changed.emit()
            # Return count from both undo_stack and legacy undo_history
            return len(self.undo_stack) + len(self.redo_stack) + len(self.undo_history)

        except (OSError, json.JSONDecodeError):
            return 0

    def _migrate_v1_to_v2(self, v1_data: dict) -> None:
        """Migrate v1 batch format to v2 operation format.

        Args:
            v1_data: v1 schema data dict
        """
        for batch_data in v1_data.get("batches", []):
            try:
                batch = UndoBatch.from_dict(batch_data)
                # Convert batch to operation
                operation = UndoOperation(
                    operation_id=batch.batch_id,
                    operation_type="create",  # v1 batches assumed to be creates
                    affected_event_ids=[e.event_id for e in batch.events],
                    event_snapshots=batch.events,
                    created_at=batch.created_at,
                    description=batch.description,
                )

                # Undone batches go to redo stack, others to undo stack
                if batch.is_undone:
                    self.redo_stack.insert(0, operation)
                else:
                    self.undo_stack.append(operation)
            except (KeyError, ValueError):
                continue


    def undo(self) -> UndoOperation | None:
        """Undo the most recent operation.

        Returns:
            The operation that was undone, or None if undo stack is empty
        """
        if not self.undo_stack:
            return None

        operation = self.undo_stack.pop()
        self.redo_stack.append(operation)
        self.operation_undone.emit(operation.operation_id)
        self.history_changed.emit()
        return operation

    def redo(self) -> UndoOperation | None:
        """Redo the most recently undone operation.

        Returns:
            The operation that was redone, or None if redo stack is empty
        """
        if not self.redo_stack:
            return None

        operation = self.redo_stack.pop()
        self.undo_stack.append(operation)
        self.operation_redone.emit(operation.operation_id)
        self.history_changed.emit()
        return operation

    def add_operation(
        self,
        operation_type: str,
        affected_event_ids: list[str],
        event_snapshots: list[EnhancedCreatedEvent],
        description: str,
    ) -> str:
        """Add a new operation to the undo stack.

        Args:
            operation_type: Type of operation ("create", "update", or "delete")
            affected_event_ids: List of event IDs affected by this operation
            event_snapshots: Complete event snapshots for redo capability
            description: Human-readable description of the operation

        Returns:
            operation_id: The ID of the created operation

        Raises:
            ValueError: If operation_type is invalid or lists are empty
        """
        if operation_type not in ("create", "update", "delete"):
            raise ValueError(f"Invalid operation_type: {operation_type}")
        if not affected_event_ids:
            raise ValueError("affected_event_ids cannot be empty")
        if not event_snapshots:
            raise ValueError("event_snapshots cannot be empty")

        operation_id = uuid.uuid4().hex
        operation = UndoOperation(
            operation_id=operation_id,
            operation_type=operation_type,
            affected_event_ids=affected_event_ids,
            event_snapshots=event_snapshots,
            created_at=dt.datetime.now(),
            description=description,
        )

        self.undo_stack.append(operation)

        # Clear redo stack on new operation (standard UX)
        if self.redo_stack:
            self.redo_stack.clear()
            self.redo_stack_cleared.emit()

        # Trim history if needed
        if len(self.undo_stack) > self.max_history:
            self.undo_stack = self.undo_stack[-self.max_history :]

        self.operation_created.emit(operation_id)
        self.history_changed.emit()

        return operation_id

    def add_batch(self, events: list[EnhancedCreatedEvent], description: str) -> str:
        """Add a new batch of events to the undo history (backwards compatibility).

        Args:
            events: List of created events
            description: Human-readable description of the batch

        Returns:
            batch_id: The ID of the created batch
        """
        if not events:
            return ""

        batch_id = events[0].batch_id if events else uuid.uuid4().hex

        batch = UndoBatch(
            batch_id=batch_id,
            created_at=dt.datetime.now(),
            events=events,
            description=description,
            is_undone=False,
        )

        # Insert at beginning (most recent first)
        self.undo_history.insert(0, batch)

        # Maintain history size limit
        if len(self.undo_history) > self.max_history:
            self.undo_history = self.undo_history[: self.max_history]

        self.history_changed.emit()
        return batch_id

    def undo_batch(self, batch_id: str) -> list[EnhancedCreatedEvent]:
        """Undo an entire batch of events.

        Args:
            batch_id: ID of the batch to undo

        Returns:
            List of events that were undone

        Raises:
            ValueError: If batch_id not found or already undone
        """
        batch = self._find_batch(batch_id)
        if batch is None:
            raise ValueError(f"Batch {batch_id} not found")

        if batch.is_undone:
            raise ValueError(f"Batch {batch_id} already undone")

        batch.is_undone = True
        self.history_changed.emit()
        self.batch_undone.emit(batch_id)

        return batch.events

    def undo_events(
        self, batch_id: str, event_ids: list[str]
    ) -> list[EnhancedCreatedEvent]:
        """Undo specific events within a batch.

        Args:
            batch_id: ID of the batch containing events
            event_ids: List of event IDs to undo

        Returns:
            List of events that were undone

        Raises:
            ValueError: If batch_id not found or events not in batch
        """
        batch = self._find_batch(batch_id)
        if batch is None:
            raise ValueError(f"Batch {batch_id} not found")

        # Find the events to undo
        events_to_undo = []
        event_id_set = set(event_ids)

        for event in batch.events:
            if event.event_id in event_id_set:
                events_to_undo.append(event)

        if len(events_to_undo) != len(event_ids):
            found_ids = {event.event_id for event in events_to_undo}
            missing_ids = set(event_ids) - found_ids
            raise ValueError(f"Events not found in batch: {missing_ids}")

        # If all events in batch are undone, mark batch as undone
        if len(events_to_undo) == len(batch.events):
            batch.is_undone = True

        self.history_changed.emit()
        self.events_undone.emit(batch_id, event_ids)

        return events_to_undo

    def get_undoable_batches(self) -> list[UndoBatch]:
        """Get all undoable batches (backwards compatibility).

        Returns operations from undo_stack first, then legacy undo_history batches.
        This supports both new operation-based code and old batch-based code.
        """
        batches = []
        
        # First, convert operations from undo_stack
        for operation in self.undo_stack:
            batch = UndoBatch(
                batch_id=operation.operation_id,
                created_at=operation.created_at,
                events=operation.event_snapshots,
                description=operation.description,
                is_undone=False,
            )
            batches.append(batch)
        
        # Then, add legacy batches from undo_history that aren't undone
        # (only if undo_stack is empty to avoid duplication)
        if not self.undo_stack:
            for batch in self.undo_history:
                if not batch.is_undone:
                    batches.append(batch)
        
        return batches

    def get_recent_batches(self, limit: int = 5) -> list[UndoBatch]:
        """Get the most recent batches (backwards compatibility).
        
        Returns recent operations from undo_stack first, then legacy undo_history.
        """
        batches = []
        
        # First, convert operations from undo_stack
        for operation in self.undo_stack[-limit:]:
            batch = UndoBatch(
                batch_id=operation.operation_id,
                created_at=operation.created_at,
                events=operation.event_snapshots,
                description=operation.description,
                is_undone=False,
            )
            batches.append(batch)
        
        # If we don't have enough from undo_stack, add from undo_history
        if len(batches) < limit and not self.undo_stack:
            for batch in self.undo_history[:limit]:
                batches.append(batch)
        
        return batches

    def get_batch_by_id(self, batch_id: str) -> UndoBatch | None:
        """Get a specific batch by ID."""
        return self._find_batch(batch_id)

    def clear_history(self) -> None:
        """Clear all undo history."""
        self.undo_history.clear()
        self.history_changed.emit()

    def remove_old_batches(self, days: int = 30) -> int:
        """Remove batches older than specified number of days.

        Args:
            days: Age in days for cutoff

        Returns:
            Number of batches removed
        """
        cutoff_date = dt.datetime.now() - dt.timedelta(days=days)
        original_count = len(self.undo_history)

        self.undo_history = [
            batch for batch in self.undo_history if batch.created_at > cutoff_date
        ]

        removed_count = original_count - len(self.undo_history)
        if removed_count > 0:
            self.history_changed.emit()

        return removed_count

    def get_history_stats(self) -> dict[str, int]:
        """Get statistics about the undo history."""
        undoable = len(self.get_undoable_batches())
        total_events = sum(len(batch.events) for batch in self.undo_history)
        undoable_events = sum(
            len(batch.events) for batch in self.get_undoable_batches()
        )

        return {
            "total_batches": len(self.undo_history),
            "undoable_batches": undoable,
            "total_events": total_events,
            "undoable_events": undoable_events,
        }

    def _find_batch(self, batch_id: str) -> UndoBatch | None:
        """Find a batch by ID."""
        for batch in self.undo_history:
            if batch.batch_id == batch_id:
                return batch
        return None

    def can_undo(self) -> bool:
        """Check if there are any batches that can be undone."""
        return len(self.get_undoable_batches()) > 0

    def get_most_recent_batch(self) -> UndoBatch | None:
        """Get the most recent batch that can be undone."""
        undoable = self.get_undoable_batches()
        return undoable[0] if undoable else None
