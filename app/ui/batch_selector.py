"""Calendar-based batch selector widget for UPDATE/DELETE modes."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QTextCharFormat, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCalendarWidget, QTreeWidget,
    QTreeWidgetItem, QLabel, QPushButton, QDialog, QDialogButtonBox, QScrollArea
)

from app.validation import UndoBatch


class BatchSelectorWidget(QWidget):
    """Calendar-based selector for choosing undo batches.
    
    Features:
    - QCalendarWidget for date navigation
    - Dates with batches highlighted
    - QTreeWidget showing batches for selected date (±7 days)
    - Expand/collapse events within each batch
    - Single-click batch selection
    
    Signals:
        batch_selected(str): Emitted when a batch is selected (batch_id)
    """
    
    batch_selected = Signal(str)  # batch_id
    
    def __init__(self, undo_manager, parent: Optional[QWidget] = None):
        """Initialize the batch selector.
        
        Args:
            undo_manager: UndoManager instance for querying batches
            parent: Parent widget
        """
        super().__init__(parent)
        self.undo_manager = undo_manager
        self._selected_batch_id: Optional[str] = None
        self._batch_item_map = {}  # Maps QTreeWidgetItem -> batch_id
        self._init_ui()
        self._populate_batches_for_date(QDate.currentDate())
    
    def _init_ui(self):
        """Initialize UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Left side: Calendar
        calendar_layout = QVBoxLayout()
        calendar_label = QLabel("Select Date:")
        calendar_label.setStyleSheet("font-weight: bold;")
        calendar_layout.addWidget(calendar_label)
        
        self.calendar = QCalendarWidget()
        self.calendar.clicked.connect(self._on_date_selected)
        calendar_layout.addWidget(self.calendar)
        
        # Highlight dates with batches
        self._highlight_dates_with_batches()
        
        layout.addLayout(calendar_layout, 1)
        
        # Right side: Batch tree
        tree_layout = QVBoxLayout()
        tree_label = QLabel("Batches (±7 days):")
        tree_label.setStyleSheet("font-weight: bold;")
        tree_layout.addWidget(tree_label)
        
        self.batch_tree = QTreeWidget()
        self.batch_tree.setHeaderLabels(["Batch", "Time", "Events"])
        self.batch_tree.setColumnCount(3)
        self.batch_tree.itemClicked.connect(self._on_batch_item_clicked)
        tree_layout.addWidget(self.batch_tree)
        
        layout.addLayout(tree_layout, 1)
    
    def _highlight_dates_with_batches(self):
        """Highlight calendar dates that have batches."""
        # Get all undoable batches
        all_batches = self.undo_manager.get_undoable_batches()
        
        # Collect all dates with events
        dates_with_events = set()
        for batch in all_batches:
            for event in batch.events:
                dates_with_events.add(event.start_time.date())
        
        # Apply formatting to highlighted dates
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold)
        fmt.setForeground(QColor("#0066cc"))
        
        for date in dates_with_events:
            q_date = QDate(date.year, date.month, date.day)
            self.calendar.setDateTextFormat(q_date, fmt)
    
    def _on_date_selected(self, q_date: QDate):
        """Handle calendar date selection."""
        date = q_date.toPython()
        self._populate_batches_for_date(q_date)
    
    def _populate_batches_for_date(self, q_date: QDate):
        """Populate batch tree for the selected date.
        
        Args:
            q_date: QDate object for the selected date
        """
        date = q_date.toPython()
        self.batch_tree.clear()
        self._batch_item_map = {}
        
        # Get batches for the selected date (±7 days)
        batches = self.undo_manager.get_batches_for_date(date, day_range=7)
        
        if not batches:
            item = QTreeWidgetItem(["No batches found for this date range"])
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.batch_tree.addTopLevelItem(item)
            return
        
        # Add each batch as a top-level item
        for batch in batches:
            # Batch item: "Batch [type] - N events"
            event_count = len(batch.events)
            batch_text = f"Batch ({batch.batch_id[:8]}) - {event_count} event{'s' if event_count != 1 else ''}"
            batch_time = batch.created_at.strftime("%Y-%m-%d %H:%M") if batch.created_at else "Unknown"
            
            batch_item = QTreeWidgetItem()
            batch_item.setText(0, batch_text)
            batch_item.setText(1, batch_time)
            batch_item.setText(2, str(event_count))
            batch_item.setData(0, Qt.UserRole, batch.batch_id)
            
            self._batch_item_map[batch_item] = batch.batch_id
            self.batch_tree.addTopLevelItem(batch_item)
            
            # Add events as child items
            for event in batch.events:
                event_text = event.event_name or "(No name)"
                event_date = event.start_time.strftime("%Y-%m-%d") if event.start_time else "Unknown"
                
                event_item = QTreeWidgetItem()
                event_item.setText(0, f"  • {event_text}")
                event_item.setText(1, event_date)
                event_item.setFlags(event_item.flags() & ~Qt.ItemIsSelectable)
                
                batch_item.addChild(event_item)
            
            # Keep batch collapsed by default
            self.batch_tree.collapseItem(batch_item)
    
    def _on_batch_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle batch item selection."""
        if item not in self._batch_item_map:
            return
        
        batch_id = self._batch_item_map[item]
        self._selected_batch_id = batch_id
        self.batch_selected.emit(batch_id)
    
    def get_selected_batch_id(self) -> Optional[str]:
        """Get the currently selected batch ID."""
        return self._selected_batch_id


class BatchSelectorDialog(QDialog):
    """Modal dialog containing BatchSelectorWidget.
    
    Returns the selected batch_id through the dialog result.
    """
    
    def __init__(self, undo_manager, parent: Optional[QWidget] = None):
        """Initialize the batch selector dialog.
        
        Args:
            undo_manager: UndoManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Select Batch")
        self.setGeometry(100, 100, 900, 500)
        
        self.undo_manager = undo_manager
        self._selected_batch_id: Optional[str] = None
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize dialog UI."""
        layout = QVBoxLayout(self)
        
        # Batch selector widget
        self.selector = BatchSelectorWidget(self.undo_manager)
        self.selector.batch_selected.connect(self._on_batch_selected)
        layout.addWidget(self.selector)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _on_batch_selected(self, batch_id: str):
        """Handle batch selection."""
        self._selected_batch_id = batch_id
    
    def _on_accept(self):
        """Handle OK button."""
        if self._selected_batch_id:
            self.accept()
        else:
            # No batch selected, don't close dialog
            pass
    
    def get_selected_batch_id(self) -> Optional[str]:
        """Get the selected batch ID after dialog acceptance."""
        return self._selected_batch_id
