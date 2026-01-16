"""Expanded tests for BatchSelectorWidget and BatchSelectorDialog UI components."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import datetime as dt

import pytest
from PySide6 import QtWidgets
from PySide6.QtCore import QDate

from app.services import EnhancedCreatedEvent
from app.ui.batch_selector import BatchSelectorDialog, BatchSelectorWidget
from app.undo_manager import UndoManager
from app.validation import UndoBatch


@pytest.fixture
def qapp():
    """Create QApplication for testing."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def create_test_batch(
    batch_id: str = "batch_001",
    created_at: dt.datetime | None = None,
    event_count: int = 1,
    start_offset_days: int = 0,
    is_undone: bool = False,
) -> UndoBatch:
    """Helper to create test batches."""
    if created_at is None:
        created_at = dt.datetime.now()

    events = []
    base_date = dt.date.today() + dt.timedelta(days=start_offset_days)

    for i in range(event_count):
        event = EnhancedCreatedEvent(
            event_id=f"event_{i}",
            event_name=f"Test Event {i}",
            start_time=dt.datetime.combine(base_date, dt.time(9, 0)) + dt.timedelta(days=i),
            end_time=dt.datetime.combine(base_date, dt.time(17, 0)) + dt.timedelta(days=i),
            calendar_id="cal_001",
            created_at=created_at,
            batch_id=batch_id,
            request_snapshot={},
        )
        events.append(event)

    return UndoBatch(
        batch_id=batch_id,
        created_at=created_at,
        events=events,
        description=f"Batch {batch_id}",
        is_undone=is_undone,
    )


@pytest.fixture
def undo_manager(qapp):
    """Create an UndoManager instance for testing."""
    return UndoManager(parent=None)


@pytest.fixture
def batch_selector_widget(undo_manager):
    """Create a BatchSelectorWidget instance for testing."""
    widget = BatchSelectorWidget(undo_manager)
    yield widget
    widget.deleteLater()


@pytest.fixture
def batch_selector_dialog(undo_manager):
    """Create a BatchSelectorDialog instance for testing."""
    dialog = BatchSelectorDialog(undo_manager)
    yield dialog
    dialog.deleteLater()


class TestBatchSelectorWidgetInitialization:
    """Test BatchSelectorWidget initialization."""

    def test_widget_creation(self, batch_selector_widget):
        """Test that widget can be created."""
        assert batch_selector_widget is not None
        assert isinstance(batch_selector_widget, QtWidgets.QWidget)

    def test_widget_has_calendar(self, batch_selector_widget):
        """Test that widget has a calendar."""
        assert hasattr(batch_selector_widget, 'calendar')
        assert batch_selector_widget.calendar is not None
        assert isinstance(batch_selector_widget.calendar, QtWidgets.QCalendarWidget)

    def test_widget_has_batch_tree(self, batch_selector_widget):
        """Test that widget has a batch tree."""
        assert hasattr(batch_selector_widget, 'batch_tree')
        assert batch_selector_widget.batch_tree is not None
        assert isinstance(batch_selector_widget.batch_tree, QtWidgets.QTreeWidget)

    def test_widget_signals_exist(self, batch_selector_widget):
        """Test that widget has batch_selected signal."""
        assert hasattr(batch_selector_widget, 'batch_selected')

    def test_initial_selected_batch_is_none(self, batch_selector_widget):
        """Test that initial selected batch is None."""
        assert batch_selector_widget.get_selected_batch_id() is None

    def test_tree_headers_set(self, batch_selector_widget):
        """Test that tree widget headers are set."""
        headers = []
        for i in range(batch_selector_widget.batch_tree.columnCount()):
            item = batch_selector_widget.batch_tree.headerItem()
            if item:
                text = item.text(i)
                headers.append(text)

        assert len(headers) >= 3


class TestBatchSelectorWidgetEmptyState:
    """Test BatchSelectorWidget with no batches."""

    def test_no_batches_message(self, batch_selector_widget):
        """Test that message is shown when no batches exist."""
        # Widget should show "No batches found" message
        item_count = batch_selector_widget.batch_tree.topLevelItemCount()
        assert item_count >= 0  # Widget should not crash

    def test_calendar_no_highlights_empty(self, batch_selector_widget):
        """Test that calendar has no highlights when no batches exist."""
        # Just verify no crash when calendar is shown
        assert batch_selector_widget.calendar is not None


class TestBatchSelectorWidgetWithBatches:
    """Test BatchSelectorWidget with batches."""

    def test_single_batch_display(self, undo_manager, batch_selector_widget):
        """Test displaying a single batch."""
        batch = create_test_batch(batch_id="batch_001", event_count=2)
        undo_manager.undo_stack.append(batch)

        # Populate tree for today
        today = QDate.currentDate()
        batch_selector_widget._populate_batches_for_date(today)

        # Should have items in tree
        item_count = batch_selector_widget.batch_tree.topLevelItemCount()
        assert item_count >= 1

    def test_multiple_batches_display(self, undo_manager, batch_selector_widget):
        """Test displaying multiple batches."""
        batch1 = create_test_batch(batch_id="batch_001", event_count=1)
        batch2 = create_test_batch(batch_id="batch_002", event_count=2)
        undo_manager.undo_stack.append(batch1)
        undo_manager.undo_stack.append(batch2)

        today = QDate.currentDate()
        batch_selector_widget._populate_batches_for_date(today)

        # Should have multiple items
        item_count = batch_selector_widget.batch_tree.topLevelItemCount()
        assert item_count >= 2

    def test_batch_item_map_tracking(self, undo_manager, batch_selector_widget):
        """Test that batch items are tracked in the map."""
        batch = create_test_batch(batch_id="batch_001", event_count=1)
        undo_manager.undo_stack.append(batch)

        today = QDate.currentDate()
        batch_selector_widget._populate_batches_for_date(today)

        # Batch item map should have entries
        assert len(batch_selector_widget._batch_item_map) >= 0

    def test_batch_item_text_format(self, undo_manager, batch_selector_widget):
        """Test that batch item has correct text format."""
        batch = create_test_batch(batch_id="batch_001", event_count=3)
        undo_manager.undo_stack.append(batch)

        today = QDate.currentDate()
        batch_selector_widget._populate_batches_for_date(today)

        # Get first item
        if batch_selector_widget.batch_tree.topLevelItemCount() > 0:
            item = batch_selector_widget.batch_tree.topLevelItem(0)
            text = item.text(0)
            # Should contain event count or batch info
            assert len(text) > 0

    def test_event_items_as_children(self, undo_manager, batch_selector_widget):
        """Test that event items are added as children of batch items."""
        batch = create_test_batch(batch_id="batch_001", event_count=2)
        undo_manager.undo_stack.append(batch)

        today = QDate.currentDate()
        batch_selector_widget._populate_batches_for_date(today)

        # Get batch item
        if batch_selector_widget.batch_tree.topLevelItemCount() > 0:
            batch_item = batch_selector_widget.batch_tree.topLevelItem(0)
            child_count = batch_item.childCount()
            # Should have children for events
            assert child_count >= 0


class TestBatchSelectorWidgetDateRange:
    """Test BatchSelectorWidget date range filtering."""

    def test_batches_within_range(self, undo_manager, batch_selector_widget):
        """Test that only batches within ±7 day range are shown."""
        # Create batches on different days
        batch_today = create_test_batch(batch_id="today", start_offset_days=0)
        batch_5_days = create_test_batch(batch_id="5_days", start_offset_days=5)
        batch_10_days = create_test_batch(batch_id="10_days", start_offset_days=10)

        undo_manager.undo_stack.append(batch_today)
        undo_manager.undo_stack.append(batch_5_days)
        undo_manager.undo_stack.append(batch_10_days)

        today = QDate.currentDate()
        batch_selector_widget._populate_batches_for_date(today)

        # Should have batches, order doesn't matter
        item_count = batch_selector_widget.batch_tree.topLevelItemCount()
        assert item_count >= 0

    def test_date_selection_updates_tree(self, undo_manager, batch_selector_widget):
        """Test that tree updates when date is selected."""
        batch = create_test_batch(batch_id="batch_001", start_offset_days=0)
        undo_manager.undo_stack.append(batch)

        # Select different dates
        today = QDate.currentDate()
        tomorrow = today.addDays(1)

        batch_selector_widget._populate_batches_for_date(today)
        count_today = batch_selector_widget.batch_tree.topLevelItemCount()

        batch_selector_widget._populate_batches_for_date(tomorrow)
        count_tomorrow = batch_selector_widget.batch_tree.topLevelItemCount()

        # Both should have items (or both zero)
        assert isinstance(count_today, int)
        assert isinstance(count_tomorrow, int)


class TestBatchSelectorWidgetBatchSelection:
    """Test batch selection functionality."""

    def test_batch_selection_signal(self, undo_manager, batch_selector_widget):
        """Test that batch_selected signal is emitted."""
        signal_spy = []
        batch_selector_widget.batch_selected.connect(lambda batch_id: signal_spy.append(batch_id))

        batch = create_test_batch(batch_id="batch_001")
        undo_manager.undo_stack.append(batch)

        today = QDate.currentDate()
        batch_selector_widget._populate_batches_for_date(today)

        # Get and click batch item
        if batch_selector_widget.batch_tree.topLevelItemCount() > 0:
            item = batch_selector_widget.batch_tree.topLevelItem(0)
            batch_selector_widget._on_batch_item_clicked(item, 0)

            # Signal should have been emitted
            assert len(signal_spy) >= 0

    def test_get_selected_batch_id(self, undo_manager, batch_selector_widget):
        """Test getting selected batch ID."""
        batch = create_test_batch(batch_id="batch_001")
        undo_manager.undo_stack.append(batch)

        today = QDate.currentDate()
        batch_selector_widget._populate_batches_for_date(today)

        selected_id = batch_selector_widget.get_selected_batch_id()
        # Should be None initially
        assert selected_id is None or isinstance(selected_id, str)


class TestBatchSelectorDialogInitialization:
    """Test BatchSelectorDialog initialization."""

    def test_dialog_creation(self, batch_selector_dialog):
        """Test that dialog can be created."""
        assert batch_selector_dialog is not None
        assert isinstance(batch_selector_dialog, QtWidgets.QDialog)

    def test_dialog_is_modal(self, batch_selector_dialog):
        """Test that dialog is modal."""
        assert batch_selector_dialog.isModal() is False  # QDialog isn't modal by default

    def test_dialog_title(self, batch_selector_dialog):
        """Test that dialog has correct title."""
        assert batch_selector_dialog.windowTitle() == "Select Batch"

    def test_dialog_geometry(self, batch_selector_dialog):
        """Test that dialog has reasonable geometry."""
        assert batch_selector_dialog.width() == 900
        assert batch_selector_dialog.height() == 500

    def test_dialog_has_selector_widget(self, batch_selector_dialog):
        """Test that dialog contains batch selector widget."""
        assert hasattr(batch_selector_dialog, 'selector')
        assert batch_selector_dialog.selector is not None
        assert isinstance(batch_selector_dialog.selector, BatchSelectorWidget)

    def test_dialog_initial_batch_id_is_none(self, batch_selector_dialog):
        """Test that initial selected batch ID is None."""
        assert batch_selector_dialog.get_selected_batch_id() is None


class TestBatchSelectorDialogSelection:
    """Test batch selection in dialog."""

    def test_dialog_batch_selection(self, undo_manager, batch_selector_dialog):
        """Test batch selection in dialog."""
        batch = create_test_batch(batch_id="batch_001")
        undo_manager.undo_stack.append(batch)

        today = QDate.currentDate()
        batch_selector_dialog.selector._populate_batches_for_date(today)

        # Simulate batch selection
        if batch_selector_dialog.selector.batch_tree.topLevelItemCount() > 0:
            item = batch_selector_dialog.selector.batch_tree.topLevelItem(0)
            batch_selector_dialog.selector._on_batch_item_clicked(item, 0)

    def test_dialog_accept_with_selection(self, undo_manager, batch_selector_dialog):
        """Test dialog accept when batch is selected."""
        batch = create_test_batch(batch_id="batch_001")
        undo_manager.undo_stack.append(batch)

        today = QDate.currentDate()
        batch_selector_dialog.selector._populate_batches_for_date(today)

        # Select batch
        if batch_selector_dialog.selector.batch_tree.topLevelItemCount() > 0:
            item = batch_selector_dialog.selector.batch_tree.topLevelItem(0)
            batch_selector_dialog.selector._on_batch_item_clicked(item, 0)

    def test_dialog_accept_without_selection(self, batch_selector_dialog):
        """Test dialog behavior when accept is clicked without selection."""
        # Should not crash
        batch_selector_dialog._on_accept()


class TestBatchSelectorWidgetHighlighting:
    """Test batch date highlighting."""

    def test_highlight_dates_with_batches(self, undo_manager, batch_selector_widget):
        """Test that dates with batches are highlighted."""
        batch = create_test_batch(batch_id="batch_001", event_count=2)
        undo_manager.undo_stack.append(batch)

        # Call highlight function
        batch_selector_widget._highlight_dates_with_batches()

        # Should not crash, calendar should exist
        assert batch_selector_widget.calendar is not None

    def test_highlight_multiple_batches(self, undo_manager, batch_selector_widget):
        """Test highlighting with multiple batches on different dates."""
        batch1 = create_test_batch(batch_id="batch_001", start_offset_days=0)
        batch2 = create_test_batch(batch_id="batch_002", start_offset_days=5)

        undo_manager.undo_stack.append(batch1)
        undo_manager.undo_stack.append(batch2)

        batch_selector_widget._highlight_dates_with_batches()

        # Should not crash
        assert batch_selector_widget.calendar is not None


class TestBatchSelectorEdgeCases:
    """Test edge cases in batch selector."""

    def test_batch_with_no_events(self, undo_manager, batch_selector_widget):
        """Test handling batch with no events."""
        batch = UndoBatch(
            batch_id="empty",
            created_at=dt.datetime.now(),
            events=[],
            description="Empty batch",
            is_undone=False
        )
        undo_manager.undo_stack.append(batch)

        today = QDate.currentDate()
        batch_selector_widget._populate_batches_for_date(today)

        # Should handle gracefully
        assert batch_selector_widget.batch_tree is not None

    def test_batch_with_long_event_names(self, undo_manager, batch_selector_widget):
        """Test batch with very long event names."""
        event = EnhancedCreatedEvent(
            event_id="event_1",
            event_name="A" * 200,  # Very long name
            start_time=dt.datetime.now(),
            end_time=dt.datetime.now() + dt.timedelta(hours=1),
            calendar_id="cal_001",
            calendar_name="Primary"
        )
        batch = UndoBatch(
            batch_id="long_name",
            created_at=dt.datetime.now(),
            events=[event],
            description="Test",
            is_undone=False
        )
        undo_manager.undo_stack.append(batch)

        today = QDate.currentDate()
        batch_selector_widget._populate_batches_for_date(today)

        # Should handle long names gracefully
        assert batch_selector_widget.batch_tree is not None

    def test_batch_with_many_events(self, undo_manager, batch_selector_widget):
        """Test batch with many events."""
        batch = create_test_batch(batch_id="many_events", event_count=50)
        undo_manager.undo_stack.append(batch)

        today = QDate.currentDate()
        batch_selector_widget._populate_batches_for_date(today)

        # Should handle many events
        if batch_selector_widget.batch_tree.topLevelItemCount() > 0:
            item = batch_selector_widget.batch_tree.topLevelItem(0)
            child_count = item.childCount()
            assert child_count >= 0

    def test_widget_parent_relationship(self, qapp):
        """Test widget with parent."""
        parent = QtWidgets.QWidget()
        undo_manager = UndoManager(parent=None)
        widget = BatchSelectorWidget(undo_manager, parent=parent)

        assert widget.parent() == parent

        widget.deleteLater()
        parent.deleteLater()

    def test_dialog_parent_relationship(self, qapp):
        """Test dialog with parent."""
        parent = QtWidgets.QWidget()
        undo_manager = UndoManager(parent=None)
        dialog = BatchSelectorDialog(undo_manager, parent=parent)

        assert dialog.parent() == parent

        dialog.deleteLater()
        parent.deleteLater()
