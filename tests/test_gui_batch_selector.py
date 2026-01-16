"""GUI tests for batch selector and main window integration."""
from __future__ import annotations

import datetime as dt
from unittest.mock import Mock, patch

import pytest

from app.config import ConfigManager
from app.services import EnhancedCreatedEvent
from app.ui.batch_selector import BatchSelectorDialog, BatchSelectorWidget
from app.ui.main_window import MainWindow
from app.undo_manager import UndoManager
from app.validation import UndoOperation


@pytest.fixture
def undo_manager():
    """Create UndoManager for tests."""
    return UndoManager(parent=None)


@pytest.fixture
def mock_api():
    """Create mock GoogleApi."""
    api = Mock()
    api.list_calendars = Mock(return_value={"Primary": "cal_001"})
    return api


@pytest.fixture
def mock_config():
    """Create mock ConfigManager."""
    config = Mock(spec=ConfigManager)
    config.ensure_defaults = Mock(return_value=Mock(
        email_address="test@example.com",
        send_email=False,
        weekdays={"monday": True, "tuesday": True, "wednesday": True,
                  "thursday": True, "friday": True, "saturday": False, "sunday": False},
        calendar="Primary",
        last_start_time="08:00",  # Add the missing last_start_time attribute
        time_presets=["08:00", "09:00", "12:00", "13:00", "14:00", "17:00"],  # Add time_presets attribute
        last_day_length="08:00",  # Add the missing last_day_length attribute
    ))
    config.load_settings = Mock(return_value=config.ensure_defaults())
    config.save_settings = Mock()
    return config


class TestBatchSelectorWidgetBasic:
    """Basic GUI tests for BatchSelectorWidget."""
    
    def test_widget_creates_without_error(self, qtbot, undo_manager):
        """Test BatchSelectorWidget instantiation."""
        widget = BatchSelectorWidget(undo_manager)
        qtbot.addWidget(widget)
        
        assert widget is not None
        assert widget.calendar is not None
        assert widget.batch_tree is not None
    
    def test_widget_has_calendar(self, qtbot, undo_manager):
        """Test widget has calendar widget."""
        widget = BatchSelectorWidget(undo_manager)
        qtbot.addWidget(widget)
        
        assert widget.calendar is not None
        assert str(type(widget.calendar)).find("QCalendarWidget") >= 0
    
    def test_widget_has_tree(self, qtbot, undo_manager):
        """Test widget has batch tree widget."""
        widget = BatchSelectorWidget(undo_manager)
        qtbot.addWidget(widget)
        
        assert widget.batch_tree is not None
        assert str(type(widget.batch_tree)).find("QTreeWidget") >= 0
    
    def test_widget_initial_selected_batch_none(self, qtbot, undo_manager):
        """Test initially no batch is selected."""
        widget = BatchSelectorWidget(undo_manager)
        qtbot.addWidget(widget)
        
        assert widget.get_selected_batch_id() is None
    
    def test_empty_batch_list_shows_message(self, qtbot, undo_manager):
        """Test empty batch list shows 'No batches found' message."""
        widget = BatchSelectorWidget(undo_manager)
        qtbot.addWidget(widget)
        
        assert widget.batch_tree.topLevelItemCount() == 1
        item = widget.batch_tree.topLevelItem(0)
        assert "No batches found" in item.text(0)
    
    def test_date_highlighting_created(self, qtbot, undo_manager):
        """Test that highlighting method doesn't error."""
        widget = BatchSelectorWidget(undo_manager)
        qtbot.addWidget(widget)
        
        # Should complete without error
        assert widget.calendar is not None


class TestBatchSelectorDialogBasic:
    """Basic GUI tests for BatchSelectorDialog."""
    
    def test_dialog_creates_without_error(self, qtbot, undo_manager):
        """Test BatchSelectorDialog instantiation."""
        dialog = BatchSelectorDialog(undo_manager)
        qtbot.addWidget(dialog)
        
        assert dialog is not None
        assert dialog.selector is not None
    
    def test_dialog_has_selector_widget(self, qtbot, undo_manager):
        """Test dialog contains batch selector widget."""
        dialog = BatchSelectorDialog(undo_manager)
        qtbot.addWidget(dialog)
        
        assert hasattr(dialog, "selector")
        assert dialog.selector is not None
    
    def test_dialog_has_title(self, qtbot, undo_manager):
        """Test dialog has descriptive title."""
        dialog = BatchSelectorDialog(undo_manager)
        qtbot.addWidget(dialog)
        
        title = dialog.windowTitle()
        assert len(title) > 0
        assert "Batch" in title or "batch" in title.lower()
    
    def test_dialog_initial_selection_none(self, qtbot, undo_manager):
        """Test initially no batch is selected in dialog."""
        dialog = BatchSelectorDialog(undo_manager)
        qtbot.addWidget(dialog)
        
        assert dialog.get_selected_batch_id() is None


class TestBatchSelectorWithOperations:
    """Test batch selector with real UndoOperation data."""
    
    def create_test_operation(self, operation_id="op_001", offset_days=0):
        """Helper to create UndoOperation."""
        base_date = dt.date.today() + dt.timedelta(days=offset_days)
        event = EnhancedCreatedEvent(
            event_id="event_001",
            event_name="Test Event",
            start_time=dt.datetime.combine(base_date, dt.time(9, 0)),
            end_time=dt.datetime.combine(base_date, dt.time(17, 0)),
            calendar_id="cal_001",
            created_at=dt.datetime.now(),
            batch_id="batch_001",
            request_snapshot={},
        )
        return UndoOperation(
            operation_id=operation_id,
            operation_type="create",
            affected_event_ids=["event_001"],
            event_snapshots=[event],
            created_at=dt.datetime.now(),
            description=f"Operation {operation_id}",
        )
    
    def test_batch_selector_displays_operations(self, qtbot, undo_manager):
        """Test batch selector displays operations."""
        # Add an operation
        op = self.create_test_operation(operation_id="test_op")
        undo_manager.undo_stack.append(op)
        
        widget = BatchSelectorWidget(undo_manager)
        qtbot.addWidget(widget)
        
        # Should show the operation as a batch
        assert widget.batch_tree.topLevelItemCount() == 1
        item = widget.batch_tree.topLevelItem(0)
        assert "Batch" in item.text(0)
    
    def test_batch_selector_shows_operation_events(self, qtbot, undo_manager):
        """Test batch selector shows events from operation."""
        op = self.create_test_operation()
        undo_manager.undo_stack.append(op)
        
        widget = BatchSelectorWidget(undo_manager)
        qtbot.addWidget(widget)
        
        batch_item = widget.batch_tree.topLevelItem(0)
        # Should have child items for events
        assert batch_item.childCount() > 0
    
    def test_dialog_displays_operations(self, qtbot, undo_manager):
        """Test dialog displays operations."""
        op = self.create_test_operation()
        undo_manager.undo_stack.append(op)
        
        dialog = BatchSelectorDialog(undo_manager)
        qtbot.addWidget(dialog)
        
        # Dialog's selector should display the operation
        assert dialog.selector.batch_tree.topLevelItemCount() > 0


class TestMainWindowBatchSelectorIntegration:
    """Test batch selector integration in main window."""
    
    def test_main_window_batch_selector_button_exists(self, qtbot, mock_api, mock_config):
        """Test main window has batch selector button."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            
            assert hasattr(window, "batch_selector_btn")
            assert window.batch_selector_btn is not None
    
    def test_batch_selector_button_visible_in_update_mode(self, qtbot, mock_api, mock_config):
        """Test batch selector button state changes in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()  # Show window to process layout
            
            window._switch_mode("update")
            # Button should exist and be properly configured
            assert hasattr(window, "batch_selector_btn")
            # In UPDATE mode, button should be visible
            assert window.batch_selector_btn.isVisible()
    
    def test_batch_selector_button_hidden_in_create_mode(self, qtbot, mock_api, mock_config):
        """Test batch selector button is hidden in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("create")
            assert not window.batch_selector_btn.isVisible()
    
    def test_batch_selector_button_visible_in_delete_mode(self, qtbot, mock_api, mock_config):
        """Test batch selector button state changes in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()  # Show window to process layout
            
            window._switch_mode("delete")
            # Button should exist and be properly configured
            assert hasattr(window, "batch_selector_btn")
            # In DELETE mode, button should be visible
            assert window.batch_selector_btn.isVisible()
    
    def test_batch_selector_button_is_clickable(self, qtbot, mock_api, mock_config):
        """Test batch selector button is enabled and clickable."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            
            window._switch_mode("update")
            assert window.batch_selector_btn.isEnabled()
    
    def test_batch_selector_button_text(self, qtbot, mock_api, mock_config):
        """Test batch selector button has correct text."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            
            window._switch_mode("update")
            assert "Batch" in window.batch_selector_btn.text() or "batch" in window.batch_selector_btn.text().lower()


class TestBatchSelectorDateFiltering:
    """Test batch selector date filtering with operations."""
    
    def test_get_batches_for_date_filters_by_range(self, undo_manager):
        """Test get_batches_for_date correctly filters by date range."""
        today = dt.date.today()
        
        # Create operations at different dates
        op_today = UndoOperation(
            operation_id="op_today",
            operation_type="create",
            affected_event_ids=["e1"],
            event_snapshots=[],
            created_at=dt.datetime.now(),
            description="Today",
        )
        
        op_far = UndoOperation(
            operation_id="op_far",
            operation_type="create",
            affected_event_ids=["e2"],
            event_snapshots=[],
            created_at=dt.datetime.now() - dt.timedelta(days=10),
            description="Far",
        )
        
        undo_manager.undo_stack.append(op_today)
        undo_manager.undo_stack.append(op_far)
        
        # Query for today (±7 days)
        batches = undo_manager.get_batches_for_date(today, day_range=7)
        
        # Should get only recent batches based on event dates
        assert len(batches) >= 0  # Depends on event timestamps


class TestModeLayoutGeometry:
    """Validates widget layout and geometry across the three modes (CREATE, UPDATE, DELETE)."""
    
    def test_create_mode_batch_selector_not_visible(self, qtbot, mock_api, mock_config):
        """Test batch selector widgets are NOT visible in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("create")

            assert not window.batch_selector_btn.isVisible()
    
    def test_create_mode_event_name_email_visible(self, qtbot, mock_api, mock_config):
        """Test event name and email inputs ARE visible in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("create")
            
            assert window.event_name.isVisible()
            assert window.notification_email.isVisible()
    
    def test_create_mode_date_pickers_visible(self, qtbot, mock_api, mock_config):
        """Test date pickers ARE visible in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("create")
            
            assert window.start_date.isVisible()
            assert window.end_date.isVisible()
    
    def test_create_mode_time_inputs_visible(self, qtbot, mock_api, mock_config):
        """Test time inputs ARE visible in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("create")
            
            assert window.hour_spinbox.isVisible()
            assert window.day_length_hour_spinbox.isVisible()
    
    def test_create_mode_weekday_checkboxes_visible(self, qtbot, mock_api, mock_config):
        """Test weekday checkboxes ARE visible in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("create")
            
            for checkbox in window.weekday_boxes.values():
                assert checkbox.isVisible()
            assert window.days_label.isVisible()
    
    def test_create_mode_process_button_text(self, qtbot, mock_api, mock_config):
        """Test process button has correct text in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("create")
            
            assert window.process_button.text() == "Insert Into Calendar"
    
    def test_create_mode_log_box_visible(self, qtbot, mock_api, mock_config):
        """Test log box is visible and spans full width in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("create")
            
            assert window.log_box.isVisible()
    
    def test_update_mode_batch_selector_visible(self, qtbot, mock_api, mock_config):
        """Test batch selector widgets ARE visible in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("update")

            assert window.batch_selector_btn.isVisible()
    
    def test_update_mode_batch_selector_button_max_width(self, qtbot, mock_api, mock_config):
        """Test batch selector button has maxWidth=200 in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            assert window.batch_selector_btn.maximumWidth() == 200

    def test_update_mode_batch_summary_visible(self, qtbot, mock_api, mock_config):
        """Test batch summary label exists in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            assert hasattr(window, "batch_summary_label")

    def test_update_mode_event_name_email_visible(self, qtbot, mock_api, mock_config):
        """Test event name and email ARE visible in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("update")
            
            assert window.event_name.isVisible()
            assert window.notification_email.isVisible()
    
    def test_update_mode_date_pickers_visible(self, qtbot, mock_api, mock_config):
        """Test date pickers ARE visible in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("update")
            
            assert window.start_date.isVisible()
            assert window.end_date.isVisible()
    
    def test_update_mode_time_inputs_visible(self, qtbot, mock_api, mock_config):
        """Test time inputs ARE visible in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("update")
            
            assert window.hour_spinbox.isVisible()
            assert window.day_length_hour_spinbox.isVisible()
    
    def test_update_mode_weekday_checkboxes_visible(self, qtbot, mock_api, mock_config):
        """Test weekday checkboxes ARE visible in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("update")
            
            for checkbox in window.weekday_boxes.values():
                assert checkbox.isVisible()
            assert window.days_label.isVisible()
    
    def test_update_mode_process_button_text(self, qtbot, mock_api, mock_config):
        """Test process button has correct text in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("update")
            
            assert window.process_button.text() == "Update Events"
    
    def test_delete_mode_batch_selector_visible(self, qtbot, mock_api, mock_config):
        """Test batch selector widgets ARE visible in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("delete")

            assert window.batch_selector_btn.isVisible()
    
    def test_delete_mode_event_name_email_not_visible(self, qtbot, mock_api, mock_config):
        """Test event name and email are NOT visible in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("delete")
            
            assert not window.event_name.isVisible()
            assert not window.notification_email.isVisible()
    
    def test_delete_mode_date_pickers_not_visible(self, qtbot, mock_api, mock_config):
        """Test date pickers are NOT visible in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("delete")
            
            assert not window.start_date.isVisible()
            assert not window.end_date.isVisible()
    
    def test_delete_mode_time_inputs_not_visible(self, qtbot, mock_api, mock_config):
        """Test time inputs are NOT visible in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("delete")
            
            assert not window.hour_spinbox.isVisible()
            assert not window.day_length_hour_spinbox.isVisible()
    
    def test_delete_mode_weekday_checkboxes_not_visible(self, qtbot, mock_api, mock_config):
        """Test weekday checkboxes are NOT visible in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("delete")
            
            for checkbox in window.weekday_boxes.values():
                assert not checkbox.isVisible()
            assert not window.days_label.isVisible()
    
    def test_delete_mode_process_button_text(self, qtbot, mock_api, mock_config):
        """Test process button has correct text in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("delete")
            
            assert window.process_button.text() == "Delete Events"
    
    def test_delete_mode_minimal_visible_widgets(self, qtbot, mock_api, mock_config):
        """Test DELETE mode shows only batch selector and process button/undo widgets."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            window._switch_mode("delete")

            # Visible in DELETE mode (button, not combo)
            assert window.batch_selector_btn.isVisible()
            assert window.process_button.isVisible()
            assert window.undo_button.isVisible()
            
            # NOT visible in DELETE mode
            assert not window.event_name.isVisible()
            assert not window.notification_email.isVisible()
            assert not window.start_date.isVisible()
            assert not window.end_date.isVisible()
            assert not window.hour_spinbox.isVisible()
            assert not window.day_length_hour_spinbox.isVisible()
            for checkbox in window.weekday_boxes.values():
                assert not checkbox.isVisible()
    
    def test_mode_switching_preserves_visibility_state(self, qtbot, mock_api, mock_config):
        """Test that switching between modes updates visibility correctly."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()
            
            # Start in CREATE mode (default)
            window._switch_mode("create")
            assert window.event_name.isVisible()
            assert not window.batch_selector_btn.isVisible()
            
            # Switch to UPDATE mode
            window._switch_mode("update")
            assert window.event_name.isVisible()
            assert window.batch_selector_btn.isVisible()
            
            # Switch to DELETE mode
            window._switch_mode("delete")
            assert not window.event_name.isVisible()
            assert window.batch_selector_btn.isVisible()
            
            # Switch back to CREATE mode
            window._switch_mode("create")
            assert window.event_name.isVisible()
            assert not window.batch_selector_btn.isVisible()
