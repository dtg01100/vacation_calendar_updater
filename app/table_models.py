from __future__ import annotations

from typing import Any

from PySide6 import QtCore
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from app.services import EnhancedCreatedEvent


class EventTableModel(QAbstractTableModel):
    """Table model for displaying events in a QTableView."""

    def __init__(self, events: list[EnhancedCreatedEvent], parent=None):
        super().__init__(parent)
        self._events = events
        self._headers = [
            "Event Name",
            "Date",
            "Start Time",
            "End Time",
            "Calendar",
            "Status",
        ]

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        """Return the number of rows in the model."""
        return len(self._events)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        """Return the number of columns in the model."""
        return len(self._headers)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return header data for the given section."""
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self._headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for the given index and role."""
        if not index.isValid():
            return None

        row = index.row()
        if row >= len(self._events):
            return None

        event = self._events[row]

        if role == Qt.ItemDataRole.DisplayRole:
            column = index.column()
            if column == 0:  # Event Name
                return event.event_name
            elif column == 1:  # Date
                return event.start_time.strftime("%Y-%m-%d")
            elif column == 2:  # Start Time
                return event.start_time.strftime("%H:%M")
            elif column == 3:  # End Time
                return event.end_time.strftime("%H:%M")
            elif column == 4:  # Calendar
                # Extract calendar from request snapshot
                return event.request_snapshot.get("calendar_name", "Unknown")
            elif column == 5:  # Status
                return "Created"

        elif role == Qt.ItemDataRole.ToolTipRole:
            # Show detailed information in tooltip
            return (
                f"Event: {event.event_name}\\n"
                f"Date: {event.start_time.strftime('%Y-%m-%d %H:%M')}\\n"
                f"Duration: {(event.end_time - event.start_time).total_seconds() / 3600:.1f} hours\\n"
                f"Calendar: {event.request_snapshot.get('calendar_name', 'Unknown')}\\n"
                f"Batch ID: {event.batch_id}"
            )

        elif role == Qt.ItemDataRole.UserRole:
            # Return the full event object for custom roles
            return event

        return None

    def updateEvents(self, events: list[EnhancedCreatedEvent]) -> None:
        """Update the events in the model."""
        self.beginResetModel()
        self._events = events.copy()
        self.endResetModel()

    def addEvent(self, event: EnhancedCreatedEvent) -> None:
        """Add a single event to the model."""
        self.beginInsertRows(QtCore.QModelIndex(), 0, 1)
        self._events.append(event)
        self.endInsertRows()

    def removeEvent(self, row: int) -> None:
        """Remove an event from the model."""
        if 0 <= row < len(self._events):
            self.beginRemoveRows(QtCore.QModelIndex(), row, row, 1)
            del self._events[row]
            self.endRemoveRows()

    def getEvent(self, row: int) -> EnhancedCreatedEvent | None:
        """Get an event by row index."""
        if 0 <= row < len(self._events):
            return self._events[row]
        return None


class UndoHistoryTableModel(QAbstractTableModel):
    """Table model for displaying undo history batches."""

    def __init__(self, batches: list, parent=None):
        super().__init__(parent)
        self._batches = batches
        self._headers = ["Date Created", "Description", "Events", "Status", "Actions"]

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return len(self._batches)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        return len(self._headers)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self._headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        if row >= len(self._batches):
            return None

        batch = self._batches[row]

        if role == Qt.ItemDataRole.DisplayRole:
            column = index.column()
            if column == 0:  # Date Created
                return batch.created_at.strftime("%Y-%m-%d %H:%M")
            elif column == 1:  # Description
                return batch.description
            elif column == 2:  # Events
                return f"{len(batch.events)} events"
            elif column == 3:  # Status
                return "Undone" if batch.is_undone else "Available"
            elif column == 4:  # Actions
                return "Undo" if not batch.is_undone else "N/A"

        elif role == Qt.ItemDataRole.ToolTipRole:
            status = "Undone" if batch.is_undone else "Available"
            return (
                f"Batch: {batch.description}\\n"
                f"Created: {batch.created_at.strftime('%Y-%m-%d %H:%M')}\\n"
                f"Events: {len(batch.events)}\\n"
                f"Status: {status}\\n"
                f"Batch ID: {batch.batch_id}"
            )

        elif role == Qt.ItemDataRole.UserRole:
            return batch

        return None
