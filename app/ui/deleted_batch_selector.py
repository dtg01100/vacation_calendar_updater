"""Dialog for selecting and undeleting batches from delete history."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class DeletedBatchSelectorWidget(QWidget):
    """Widget for selecting deleted batches to restore.

    Features:
    - List of all deleted batches (most recent first)
    - Shows event count and date for each batch
    - Single-click batch selection
    - Can select batches in any order for undelete

    Signals:
        batch_selected(str): Emitted when a batch is selected (batch_id)
    """

    batch_selected = Signal(str)  # batch_id

    def __init__(self, undo_manager, parent: QWidget | None = None):
        """Initialize the deleted batch selector.

        Args:
            undo_manager: UndoManager instance for querying deleted batches
            parent: Parent widget
        """
        super().__init__(parent)
        self.undo_manager = undo_manager
        self._selected_batch_id: str | None = None
        self._init_ui()
        self._populate_deleted_batches()

    def _init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_label = QLabel("Deleted Batches (most recent first):")
        header_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(header_label)

        # List of deleted batches
        self.batch_list = QListWidget()
        self.batch_list.itemClicked.connect(self._on_batch_item_clicked)
        layout.addWidget(self.batch_list)

        # Info label
        self.info_label = QLabel("Select a batch to undelete")
        self.info_label.setStyleSheet("color: #666666; font-style: italic;")
        layout.addWidget(self.info_label)

    def _populate_deleted_batches(self):
        """Populate list with all deleted batches."""
        self.batch_list.clear()

        deleted_batches = self.undo_manager.get_deleted_batches()

        if not deleted_batches:
            item = QListWidgetItem("No deleted batches")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setData(Qt.UserRole, None)
            self.batch_list.addItem(item)
            self.info_label.setText("No deleted batches to restore")
            return

        # Add each deleted batch as a list item
        # Most recent first (reversed order since batches are returned oldest first)
        for batch in reversed(deleted_batches):
            event_count = len(batch.events)
            created_date = batch.created_at.strftime("%Y-%m-%d %H:%M") if batch.created_at else "Unknown"

            # Build display text
            batch_desc = batch.description or f"Batch {batch.batch_id[:8]}"
            display_text = f"{batch_desc}\n{event_count} event{'s' if event_count != 1 else ''} • {created_date}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, batch.batch_id)
            self.batch_list.addItem(item)

        self.info_label.setText(f"{len(deleted_batches)} deleted batch{'es' if len(deleted_batches) != 1 else ''} available")

    def _on_batch_item_clicked(self, item: QListWidgetItem):
        """Handle batch item selection."""
        batch_id = item.data(Qt.UserRole)
        if batch_id:
            self._selected_batch_id = batch_id
            self.batch_selected.emit(batch_id)

    def get_selected_batch_id(self) -> str | None:
        """Get the currently selected batch ID."""
        return self._selected_batch_id

    def refresh(self):
        """Refresh the list of deleted batches."""
        self._populate_deleted_batches()


class DeletedBatchSelectorDialog(QDialog):
    """Modal dialog for selecting deleted batches to restore.

    Returns the selected batch_id through the dialog result.
    """

    def __init__(self, undo_manager, parent: QWidget | None = None):
        """Initialize the deleted batch selector dialog.

        Args:
            undo_manager: UndoManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Restore Deleted Events")
        self.setGeometry(100, 100, 600, 400)

        self.undo_manager = undo_manager
        self._selected_batch_id: str | None = None

        self._init_ui()

    def _init_ui(self):
        """Initialize dialog UI."""
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "Select a deleted batch to restore.\n"
            "Events can be restored in any order."
        )
        instructions.setStyleSheet("color: #555555; margin-bottom: 10px;")
        layout.addWidget(instructions)

        # Batch selector widget
        self.selector = DeletedBatchSelectorWidget(self.undo_manager)
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

    def get_selected_batch_id(self) -> str | None:
        """Get the selected batch ID after dialog acceptance."""
        return self._selected_batch_id
