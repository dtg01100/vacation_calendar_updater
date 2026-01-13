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
        self.max_history = max_history
        self.persistence_file = "undo_history.json"

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

        # Save v2 format (operation-based)
        data = {
            "version": 2,
            "max_history": self.max_history,
            "undo_stack": [operation.to_dict() for operation in self.undo_stack],
            "redo_stack": [operation.to_dict() for operation in self.redo_stack],
        }

        try:
            with open(file_path, "w") as f:
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
            with open(file_path) as f:
                data = json.load(f)

            version = data.get("version", 2)
            
            if version != 2:
                # Only support v2 format now
                return 0

            # Clear existing stacks
            self.undo_stack.clear()
            self.redo_stack.clear()

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

            # Restore max_history setting
            if "max_history" in data:
                self.max_history = data["max_history"]

            # Trim history if needed
            if len(self.undo_stack) > self.max_history:
                self.undo_stack = self.undo_stack[-self.max_history :]

            self.history_changed.emit()
            return len(self.undo_stack) + len(self.redo_stack)

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

    def get_undoable_batches(self) -> list[UndoBatch]:
        """Get all undoable operations as batches (backwards compatibility).

        Returns operations from undo_stack converted to batch format.
        """
        batches = []
        
        # Convert operations from undo_stack to batch format
        for operation in self.undo_stack:
            batch = UndoBatch(
                batch_id=operation.operation_id,
                created_at=operation.created_at,
                events=operation.event_snapshots,
                description=operation.description,
                is_undone=False,
            )
            batches.append(batch)
        
        return batches
    
    def get_undoable_operations(self) -> list[UndoOperation]:
        """Get all operations that can be undone (preferred API).
        
        Returns:
            List of operations from the undo stack
        """
        return list(self.undo_stack)

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
        
        # Get all undoable batches
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
        
        # Convert recent operations from undo_stack
        for operation in self.undo_stack[-limit:]:
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
            if operation.operation_id == batch_id:
                return UndoBatch(
                    batch_id=operation.operation_id,
                    created_at=operation.created_at,
                    events=operation.event_snapshots,
                    description=operation.description,
                    is_undone=False,
                )
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
        for operation in self.redo_stack:
            if operation.operation_id == operation_id:
                return operation
        return None

    def can_undo(self) -> bool:
        """Check if there are operations that can be undone."""
        return len(self.undo_stack) > 0

    def get_most_recent_batch(self) -> UndoBatch | None:
        """Get the most recent operation as a batch (backwards compatibility)."""
        if not self.undo_stack:
            return None
        operation = self.undo_stack[-1]
        return UndoBatch(
            batch_id=operation.operation_id,
            created_at=operation.created_at,
            events=operation.event_snapshots,
            description=operation.description,
            is_undone=False,
        )

