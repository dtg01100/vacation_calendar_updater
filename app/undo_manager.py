from __future__ import annotations

import datetime as dt
import json
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import QObject, Signal

from .services import EnhancedCreatedEvent
from .validation import UndoBatch


class UndoManager(QObject):
    """Manages undo history for calendar events with multi-level undo support."""

    # Signals
    history_changed = Signal()
    batch_undone = Signal(str)  # batch_id
    events_undone = Signal(str, list)  # batch_id, event_ids
    save_failed = Signal(str)  # error_message

    def __init__(self, max_history: int = 50, parent=None):
        super().__init__(parent)
        self.undo_history: List[UndoBatch] = []
        self.max_history = max_history
        self.persistence_file = "undo_history.json"

    def save_history(self, directory: str | None = None) -> None:
        """Save undo history to a JSON file.

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
            try:
                shutil.copy(file_path, backup_path)
            except (IOError, OSError) as e:
                # Continue even if backup fails - better to save without backup
                print(f"Failed to create backup: {e}")

        data = {
            "version": 1,
            "max_history": self.max_history,
            "batches": [batch.to_dict() for batch in self.undo_history],
        }

        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
        except (IOError, OSError) as e:
            # Log error and emit signal for user notification
            error_msg = f"Failed to save undo history: {e}"
            print(error_msg)
            self.save_failed.emit(error_msg)

    def load_history(self, directory: str | None = None) -> int:
        """Load undo history from a JSON file.

        Args:
            directory: Directory to load the file from (defaults to current directory)

        Returns:
            Number of batches loaded
        """
        if directory:
            file_path = Path(directory) / self.persistence_file
        else:
            file_path = Path(self.persistence_file)

        if not file_path.exists():
            return 0

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            # Handle version migration if needed in the future
            _ = data.get("version", 1)  # Reserved for future migrations

            # Clear existing history
            self.undo_history.clear()

            # Load batches
            batches_data = data.get("batches", [])
            for batch_data in batches_data:
                try:
                    batch = UndoBatch.from_dict(batch_data)
                    self.undo_history.append(batch)
                except (KeyError, ValueError) as e:
                    print(f"Skipping invalid batch in undo history: {e}")
                    continue

            # Restore max_history setting
            if "max_history" in data:
                self.max_history = data["max_history"]

            # Trim history if needed
            if len(self.undo_history) > self.max_history:
                self.undo_history = self.undo_history[: self.max_history]

            self.history_changed.emit()
            return len(self.undo_history)

        except (IOError, OSError, json.JSONDecodeError) as e:
            print(f"Failed to load undo history: {e}")
            return 0

    def add_batch(self, events: List[EnhancedCreatedEvent], description: str) -> str:
        """Add a new batch of events to the undo history.

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

    def undo_batch(self, batch_id: str) -> List[EnhancedCreatedEvent]:
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
        self, batch_id: str, event_ids: List[str]
    ) -> List[EnhancedCreatedEvent]:
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

    def get_undoable_batches(self) -> List[UndoBatch]:
        """Get all batches that can be undone (not already undone)."""
        return [batch for batch in self.undo_history if not batch.is_undone]

    def get_recent_batches(self, limit: int = 5) -> List[UndoBatch]:
        """Get the most recent batches (both undone and not undone)."""
        return self.undo_history[:limit]

    def get_batch_by_id(self, batch_id: str) -> Optional[UndoBatch]:
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

    def get_history_stats(self) -> Dict[str, int]:
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

    def _find_batch(self, batch_id: str) -> Optional[UndoBatch]:
        """Find a batch by ID."""
        for batch in self.undo_history:
            if batch.batch_id == batch_id:
                return batch
        return None

    def can_undo(self) -> bool:
        """Check if there are any batches that can be undone."""
        return len(self.get_undoable_batches()) > 0

    def get_most_recent_batch(self) -> Optional[UndoBatch]:
        """Get the most recent batch that can be undone."""
        undoable = self.get_undoable_batches()
        return undoable[0] if undoable else None
