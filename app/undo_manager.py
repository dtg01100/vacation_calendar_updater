from __future__ import annotations

import contextlib
import datetime as dt
import json
import shutil
import uuid
from pathlib import Path

try:
    from PySide6.QtCore import QObject, Signal
except ImportError:  # pragma: no cover - lightweight fallback for test environments
    class Signal:
        def __init__(self, *args, **kwargs):
            self._subscribers = []

        def connect(self, callback):
            self._subscribers.append(callback)

        def emit(self, *args, **kwargs):
            for callback in list(self._subscribers):
                callback(*args, **kwargs)

    class QObject:
        def __init__(self, *args, **kwargs):
            super().__init__()

from .services import EnhancedCreatedEvent
from .validation import UndoBatch, UndoOperation


class UndoManager(QObject):
    """Manages undo/redo history with operation-based architecture."""

    # Signals for operation-based undo/redo
    history_changed = Signal()
    operation_created = Signal(str)  # operation_id
    operation_undone = Signal(str)  # operation_id
    operation_redone = Signal(str)  # operation_id
    redo_stack_cleared = Signal()  # no parameters
    save_failed = Signal(str)  # error_message

    def __init__(self, max_history: int = 50, parent=None):
        super().__init__(parent)
        self.undo_stack: list[UndoOperation] = []
        self.redo_stack: list[UndoOperation] = []
        # Deletes are tracked separately so they don't appear in the main batch selector
        self.delete_stack: list[UndoOperation] = []
        self.delete_redo_stack: list[UndoOperation] = []
        self.max_history = max_history
        self.persistence_file = "undo_history.json"
        self.schema_version = 3

    def save_history(self, directory: str | None = None) -> None:
        """Save undo history to a JSON file (v2 operation-based schema).

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

        # Save v3 format (operation-based with separate delete stacks)
        data = {
            "version": self.schema_version,
            "max_history": self.max_history,
            "undo_stack": [operation.to_dict() for operation in self.undo_stack],
            "redo_stack": [operation.to_dict() for operation in self.redo_stack],
            "delete_stack": [operation.to_dict() for operation in self.delete_stack],
            "delete_redo_stack": [operation.to_dict() for operation in self.delete_redo_stack],
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            # Log error and emit signal for user notification
            error_msg = f"Failed to save undo history: {e}"
            self.save_failed.emit(error_msg)

    def load_history(self, directory: str | None = None) -> int:
        """Load undo history from a JSON file (v2 operation-based schema).

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
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            version = data.get("version", 2)

            if version not in (2, 3):
                # Only support v2/v3 formats now
                return 0

            # Clear existing stacks
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.delete_stack.clear()
            self.delete_redo_stack.clear()

            # Load v2/v3 format directly
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

            if version >= 3:
                for op_data in data.get("delete_stack", []):
                    try:
                        operation = UndoOperation.from_dict(op_data)
                        self.delete_stack.append(operation)
                    except (KeyError, ValueError):
                        continue

                for op_data in data.get("delete_redo_stack", []):
                    try:
                        operation = UndoOperation.from_dict(op_data)
                        self.delete_redo_stack.append(operation)
                    except (KeyError, ValueError):
                        continue

            # Restore max_history setting
            if "max_history" in data:
                self.max_history = data["max_history"]

            # Trim history if needed
            if len(self.undo_stack) > self.max_history:
                self.undo_stack = self.undo_stack[-self.max_history :]
            if len(self.delete_stack) > self.max_history:
                self.delete_stack = self.delete_stack[-self.max_history :]

            self.history_changed.emit()
            return len(self.undo_stack) + len(self.redo_stack) + len(self.delete_stack) + len(self.delete_redo_stack)

        except (OSError, json.JSONDecodeError):
            return 0


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

    def add_batch(self, events: list[EnhancedCreatedEvent], description: str) -> str:
        """Backwards-compatible helper to add a batch (treated as create operation)."""
        # Ensure batch IDs exist but preserve any provided identifiers
        batch_id = None
        for event in events:
            if getattr(event, "batch_id", None):
                batch_id = event.batch_id
                break
        if not batch_id:
            batch_id = uuid.uuid4().hex

        for event in events:
            with contextlib.suppress(Exception):
                if not getattr(event, "batch_id", None):
                    event.batch_id = batch_id

        return self.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in events],
            event_snapshots=events,
            description=description,
        )

    def add_operation(
        self,
        operation_type: str,
        affected_event_ids: list[str],
        event_snapshots: list[EnhancedCreatedEvent],
        description: str,
    ) -> str:
        """Add a new operation to the appropriate stack.

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

        if operation_type == "delete":
            target_stack = self.delete_stack
            redo_stack = self.delete_redo_stack
        else:
            target_stack = self.undo_stack
            redo_stack = self.redo_stack

        target_stack.append(operation)

        # Clear redo stack on new operation (standard UX)
        if redo_stack:
            redo_stack.clear()
            self.redo_stack_cleared.emit()

        # Trim history if needed
        if len(target_stack) > self.max_history:
            del target_stack[:-self.max_history]

        self.operation_created.emit(operation_id)
        self.history_changed.emit()

        return operation_id

    def remove_operation(self, operation_id: str, *, include_redo: bool = True) -> UndoOperation | None:
        """Remove an operation from the main stacks (create/update only).

        Args:
            operation_id: ID to remove (can be operation_id or batch_id)
            include_redo: Whether to also search the redo stack

        Returns:
            The removed operation, or None if not found.
        """

        for stack in (self.undo_stack,):
            for idx, op in enumerate(stack):
                if op.operation_id == operation_id:
                    removed = stack.pop(idx)
                    self.history_changed.emit()
                    return removed
                # Also check if any event in the operation has this batch_id
                for snapshot in getattr(op, "event_snapshots", []) or []:
                    if getattr(snapshot, "batch_id", None) == operation_id:
                        removed = stack.pop(idx)
                        self.history_changed.emit()
                        return removed

        if include_redo:
            for idx, op in enumerate(self.redo_stack):
                if op.operation_id == operation_id:
                    removed = self.redo_stack.pop(idx)
                    self.history_changed.emit()
                    return removed
                # Also check if any event in the operation has this batch_id
                for snapshot in getattr(op, "event_snapshots", []) or []:
                    if getattr(snapshot, "batch_id", None) == operation_id:
                        removed = self.redo_stack.pop(idx)
                        self.history_changed.emit()
                        return removed

        return None

    def _operations_to_batches(self, operations: list[UndoOperation | UndoBatch]) -> list[UndoBatch]:
        batches: list[UndoBatch] = []
        for operation in operations:
            if isinstance(operation, UndoBatch):
                batches.append(operation)
            else:
                batch_identifier = None
                if operation.event_snapshots:
                    batch_identifier = getattr(operation.event_snapshots[0], "batch_id", None)
                batches.append(
                    UndoBatch(
                        batch_id=batch_identifier or operation.operation_id,
                        created_at=operation.created_at,
                        events=operation.event_snapshots,
                        description=operation.description,
                        is_undone=False,
                    )
                )
        return batches

    def get_undoable_batches(self) -> list[UndoBatch]:
        """Get all undoable operations as batches (excludes delete operations)."""
        # Allow legacy UndoBatch entries to coexist for tests/backwards compatibility
        visible_ops: list[UndoOperation | UndoBatch] = []
        for op in self.undo_stack:
            if isinstance(op, UndoBatch):
                # Only include if not marked undone
                if not getattr(op, "is_undone", False):
                    visible_ops.append(op)
            else:
                if op.operation_type != "delete" and not getattr(op, "is_undone", False):
                    visible_ops.append(op)
        # Most recent first
        return list(reversed(self._operations_to_batches(visible_ops)))

    def get_deleted_batches(self) -> list[UndoBatch]:
        """Get delete operations as batches (for undelete UI)."""
        return self._operations_to_batches(list(self.delete_stack))

    def get_undoable_operations(self) -> list[UndoOperation]:
        """Get all operations that can be undone (preferred API).

        Returns:
            List of operations from the undo stack
        """
        ops: list[UndoOperation] = []
        for op in self.undo_stack:
            if isinstance(op, UndoOperation) and op.operation_type != "delete":
                ops.append(op)
        return ops

    def get_deleted_operations(self) -> list[UndoOperation]:
        """Get delete operations that can be undone (undelete)."""
        return list(self.delete_stack)

    def get_history_stats(self) -> dict[str, int]:
        """Return basic statistics about undo/redo history.

        The counts intentionally reflect only what is currently undoable or
        redoable to keep the UI messaging simple.
        """

        undoable_batches = len([op for op in self.undo_stack if isinstance(op, UndoOperation) and op.operation_type != "delete"])
        undoable_events = sum(len(op.event_snapshots) for op in self.undo_stack if isinstance(op, UndoOperation) and op.operation_type != "delete")
        redoable_batches = len(self.redo_stack)
        redoable_events = sum(len(op.event_snapshots) for op in self.redo_stack)
        undeleteable_batches = len(self.delete_stack)
        undeleteable_events = sum(len(op.event_snapshots) for op in self.delete_stack)
        redeleteable_batches = len(self.delete_redo_stack)
        redeleteable_events = sum(len(op.event_snapshots) for op in self.delete_redo_stack)

        return {
            "undoable_batches": undoable_batches,
            "undoable_events": undoable_events,
            "redoable_batches": redoable_batches,
            "redoable_events": redoable_events,
            "undeleteable_batches": undeleteable_batches,
            "undeleteable_events": undeleteable_events,
            "redeleteable_batches": redeleteable_batches,
            "redeleteable_events": redeleteable_events,
        }

    def get_batches_for_date(self, target_date: dt.date, day_range: int = 7) -> list[UndoBatch]:
        """Get batches containing events on or near a specific date.

        Args:
            target_date: The date to filter by
            day_range: How many days before/after to include (default 7)

        Returns:
            List of batches with events in the date range, most recent first
        """
        result = []
        seen_batch_ids = set()

        # Get all visible batches (non-delete), already ordered most-recent first
        all_batches = self.get_undoable_batches()

        for batch in all_batches:
            if batch.batch_id in seen_batch_ids:
                continue

            # Check if any event in this batch falls within the date range
            for event in batch.events:
                event_date = event.start_time.date()
                days_diff = abs((event_date - target_date).days)

                if days_diff <= day_range:
                    result.append(batch)
                    seen_batch_ids.add(batch.batch_id)
                    break  # Don't add batch twice

        return result

    def get_recent_batches(self, limit: int = 5) -> list[UndoBatch]:
        """Get the most recent operations as batches (backwards compatibility).

        Returns recent operations from undo_stack converted to batch format.
        """
        batches = []

        # Convert recent operations from undo_stack (non-delete)
        for operation in [op for op in self.undo_stack if isinstance(op, UndoOperation) and op.operation_type != "delete"][-limit:]:
            batch = UndoBatch(
                batch_id=operation.operation_id,
                created_at=operation.created_at,
                events=operation.event_snapshots,
                description=operation.description,
                is_undone=False,
            )
            batches.append(batch)

        return batches

    def get_batch_by_id(self, batch_id: str) -> UndoBatch | None:
        """Get a specific operation by ID as a batch (backwards compatibility)."""
        # Search in undo_stack first
        for operation in self.undo_stack:
            if isinstance(operation, UndoOperation) and operation.operation_id == batch_id and operation.operation_type != "delete":
                return UndoBatch(
                    batch_id=operation.operation_id,
                    created_at=operation.created_at,
                    events=operation.event_snapshots,
                    description=operation.description,
                    is_undone=False,
                )
            if isinstance(operation, UndoOperation) and operation.operation_type != "delete":
                for snapshot in getattr(operation, "event_snapshots", []) or []:
                    if getattr(snapshot, "batch_id", None) == batch_id:
                        return UndoBatch(
                            batch_id=batch_id,
                            created_at=operation.created_at,
                            events=operation.event_snapshots,
                            description=operation.description,
                            is_undone=getattr(operation, "is_undone", False),
                        )
            if isinstance(operation, UndoBatch) and operation.batch_id == batch_id and not getattr(operation, "is_undone", False):
                return operation
        return None

    def get_operation_by_id(self, operation_id: str) -> UndoOperation | None:
        """Get a specific operation by ID (preferred API).

        Args:
            operation_id: The operation ID to search for

        Returns:
            The operation if found, None otherwise
        """
        for operation in self.undo_stack:
            if operation.operation_id == operation_id:
                return operation
            for snapshot in getattr(operation, "event_snapshots", []) or []:
                if getattr(snapshot, "batch_id", None) == operation_id:
                    return operation
        for operation in self.redo_stack:
            if operation.operation_id == operation_id:
                return operation
            for snapshot in getattr(operation, "event_snapshots", []) or []:
                if getattr(snapshot, "batch_id", None) == operation_id:
                    return operation
        for operation in self.delete_stack:
            if operation.operation_id == operation_id:
                return operation
        for operation in self.delete_redo_stack:
            if operation.operation_id == operation_id:
                return operation
        return None

    def can_undo(self) -> bool:
        """Check if there are operations that can be undone."""
        return len([op for op in self.undo_stack if isinstance(op, UndoOperation) and op.operation_type != "delete"]) > 0

    def can_redo(self) -> bool:
        """Check if there are operations that can be redone."""
        return len(self.redo_stack) > 0

    def undo_batch(self, batch_id: str) -> None:
        """Mark a batch as undone (same as undo())."""
        for operation in self.undo_stack:
            if isinstance(operation, UndoBatch):
                if operation.batch_id == batch_id:
                    operation.is_undone = True
                    self.history_changed.emit()
                    return
            elif operation.operation_id == batch_id:
                # Mark as undone so get_undoable_batches filters it out
                operation.is_undone = True
                self.history_changed.emit()
                return
            else:
                for snapshot in getattr(operation, "event_snapshots", []) or []:
                    if getattr(snapshot, "batch_id", None) == batch_id:
                        operation.is_undone = True
                        self.history_changed.emit()
                        return

    def redo_batch(self, batch_id: str) -> None:
        """Mark a batch as redone (same as redo())."""
        for operation in self.undo_stack:
            if isinstance(operation, UndoBatch):
                if operation.batch_id == batch_id:
                    operation.is_undone = False
                    self.history_changed.emit()
                    return
            elif operation.operation_id == batch_id:
                if getattr(operation, "is_undone", False):
                    operation.is_undone = False
                    self.history_changed.emit()
                    return
            else:
                for snapshot in getattr(operation, "event_snapshots", []) or []:
                    if getattr(snapshot, "batch_id", None) == batch_id:
                        if getattr(operation, "is_undone", False):
                            operation.is_undone = False
                            self.history_changed.emit()
                        return

    def get_redoable_operations(self) -> list[UndoOperation]:
        """Get all operations that can be redone.

        Returns:
            List of operations from the redo stack
        """
        return list(self.redo_stack)

    def get_redeleteable_operations(self) -> list[UndoOperation]:
        """Get delete operations that can be redone (after an undelete)."""
        return list(self.delete_redo_stack)

    def get_redoable_batches(self) -> list[UndoBatch]:
        """Get all redoable operations as batches (mirrors get_undoable_batches()).

        Returns operations from redo_stack converted to batch format.
        """
        batches = []

        # Convert operations from redo_stack to batch format
        for operation in self.redo_stack:
            batch = UndoBatch(
                batch_id=operation.operation_id,
                created_at=operation.created_at,
                events=operation.event_snapshots,
                description=operation.description,
                is_undone=False,
            )
            batches.append(batch)

        return batches

    def get_most_recent_batch(self) -> UndoBatch | None:
        """Get the most recent operation as a batch (backwards compatibility)."""
        visible_ops = [op for op in self.undo_stack if isinstance(op, UndoOperation) and op.operation_type != "delete"]
        if not visible_ops:
            return None
        operation = visible_ops[-1]
        return UndoBatch(
            batch_id=operation.operation_id,
            created_at=operation.created_at,
            events=operation.event_snapshots,
            description=operation.description,
            is_undone=False,
        )

    # Delete-specific undo/redo (undelete/re-delete)
    def undo_delete(self) -> UndoOperation | None:
        if not self.delete_stack:
            return None
        operation = self.delete_stack.pop()
        self.delete_redo_stack.append(operation)
        self.operation_undone.emit(operation.operation_id)
        self.history_changed.emit()
        return operation

    def redo_delete(self) -> UndoOperation | None:
        if not self.delete_redo_stack:
            return None
        operation = self.delete_redo_stack.pop()
        self.delete_stack.append(operation)
        self.operation_redone.emit(operation.operation_id)
        self.history_changed.emit()
        return operation
