from __future__ import annotations

import sys
from pathlib import Path
import datetime as dt

from PySide6 import QtCore, QtGui, QtWidgets

from ..config import ConfigManager, Settings
from ..services import EnhancedCreatedEvent, GoogleApi
from ..undo_manager import UndoManager
from ..validation import (
    ScheduleRequest,
    build_schedule,
    parse_date,
    parse_time,
    validate_request,
)
from ..workers import EventCreationWorker, StartupWorker, UndoWorker, RedoWorker, DeleteWorker, UpdateWorker
from .datepicker import DatePicker
from .batch_selector import BatchSelectorDialog
from .deleted_batch_selector import DeletedBatchSelectorDialog
from . import dark_mode


class MainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        api: GoogleApi,
        config: ConfigManager,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.api = api
        self.config_manager = config
        self.undo_manager = UndoManager(parent=self)
        self.created_events: list[EnhancedCreatedEvent] = []
        self.creation_thread: QtCore.QThread | None = None
        self.undo_thread: QtCore.QThread | None = None
        self.redo_thread: QtCore.QThread | None = None
        self.delete_thread: QtCore.QThread | None = None
        self.update_thread: QtCore.QThread | None = None
        self.creation_worker: EventCreationWorker | None = None
        self.undo_worker: UndoWorker | None = None
        self.redo_worker: RedoWorker | None = None
        self.delete_worker: DeleteWorker | None = None
        self.update_worker: UpdateWorker | None = None
        
        # Mode state: 'create', 'update', or 'delete'
        self.current_mode = "create"
        self.selected_batch_for_operation: str | None = None  # batch_id for update/delete

        # Use Qt standard paths for platform-appropriate app data directory
        self._app_data_dir = Path(
            QtCore.QStandardPaths.writableLocation(
                QtCore.QStandardPaths.StandardLocation.AppDataLocation
            )
        )
        self._app_data_dir.mkdir(parents=True, exist_ok=True)
        self.undo_manager.load_history(str(self._app_data_dir))

        # Connect undo manager signals
        self.undo_manager.history_changed.connect(self._update_undo_ui)
        self.undo_manager.save_failed.connect(self._on_save_failed)

        self.setWindowTitle("Vacation Calendar Updater")
        # Set window icon for task manager/dock
        icon_path = "/app/share/icons/hicolor/512x512/apps/com.github.dtg01100.vacation_calendar_updater.png"
        if Path(icon_path).exists():
            self.setWindowIcon(QtGui.QIcon(icon_path))
        else:
            self.setWindowIcon(QtGui.QIcon.fromTheme("appointment-new"))
        self._init_services()
        self.settings = self.config_manager.ensure_defaults(
            default_email=self.user_email,
            calendar_options=self.calendar_names,
        )
        self._build_ui()
        self._setup_status_bar()
        self._apply_settings()
        self._update_validation()
        # Update undo UI with any loaded history
        self._update_undo_ui()
        # Start background loading after all UI is built
        self.progress_bar.setVisible(True)
        self._startup_worker.start()
        
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop_all_threads)
        
        # Apply dark mode styles
        self._apply_dark_mode_styles()

    def _apply_dark_mode_styles(self) -> None:
        """Apply dark mode styles if in dark mode."""
        if not dark_mode.is_dark_mode():
            return
        # All widgets have been styled during creation via dark_mode helpers
        pass

    def _open_batch_selector(self) -> None:
        """Open batch selector dialog to choose a batch for update/delete."""
        dialog = BatchSelectorDialog(self.undo_manager, parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            batch_id = dialog.get_selected_batch_id()
            if batch_id:
                batch = self.undo_manager.get_batch_by_id(batch_id)
                self.selected_batch_for_operation = batch_id
                if batch:
                    self.batch_summary_label.setText(batch.description)
                    self._update_validation()

    def _init_services(self) -> None:
        # Load defaults immediately (non-blocking)
        self.settings = self.config_manager.ensure_defaults(
            default_email="",
            calendar_options=[],
        )
        self.user_email = self.settings.email_address
        self.calendar_names: list[str] = []
        self.calendar_items: list[dict[str, str]] = []
        self.calendar_id_by_name: dict[str, str] = {}

        # Create and configure startup worker (will be started after UI is built)
        self._startup_worker = StartupWorker(self.api)
        self._startup_worker.finished.connect(self._on_startup_finished)
        self._startup_worker.error.connect(self._on_startup_error)

    def _start_loading(self) -> None:
        """Start the loading process after UI is fully initialized."""
        self.progress_bar.setVisible(True)
        self.statusBar().showMessage("Connecting to Google Calendar...")
        # Start worker immediately - _on_startup_finished will delay if UI isn't ready yet
        self._startup_worker.start()

    def _on_startup_finished(
        self, result: tuple[str, tuple[list[str], list[dict[str, str]]]]
    ) -> None:
        """Handle successful API connection."""
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("", 0)  # Clear message

        email, (calendar_names, calendar_items) = result

        # Build calendar ID mapping
        for item in calendar_items:
            summary = item.get("summary")
            cal_id = item.get("id")
            if summary and cal_id:
                self.calendar_id_by_name[summary] = cal_id

        # Update email if we got one from API AND no email is currently saved
        # This ensures we don't overwrite a user-entered email
        if email and not self.settings.email_address:
            self.settings.email_address = email
            self.notification_email.setText(email)
            # Save immediately when API provides email
            self.config_manager.save(self.settings)

        # Update calendar combo with available calendars
        self.calendar_combo.clear()
        self.calendar_combo.addItems(calendar_names)
        self.calendar_combo.setEnabled(True)
        
        # Set current calendar from settings
        if self.settings.calendar and self.settings.calendar in calendar_names:
            self.calendar_combo.setCurrentText(self.settings.calendar)
        elif calendar_names:
            self.calendar_combo.setCurrentIndex(0)

        # Update calendar_names for validation
        self.calendar_names = calendar_names

        # Re-apply settings to update weekday checkboxes
        self._apply_settings()
        self._update_validation()

        # Hide progress indicator
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Ready")

    def _on_startup_error(self, error_message: str) -> None:
        """Handle API connection error."""
        # Hide progress indicator
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Connection failed")
        QtWidgets.QMessageBox.critical(self, "Unable to connect", error_message)
        # Use defaults - app can still function with manual calendar entry
        if not self.calendar_names:
            self.calendar_combo.clear()
            self.calendar_combo.addItem("Primary")
            self.calendar_combo.setEnabled(True)
            self.calendar_names = ["Primary"]

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        central.setLayout(layout)
 
        # Row -1: Mode selector buttons at the very top
        self.mode_frame = QtWidgets.QFrame()
        dark_mode.style_mode_frame(self.mode_frame)
        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.setContentsMargins(8, 8, 8, 8)
        self.mode_frame.setLayout(mode_layout)
        
        self.mode_create_btn = QtWidgets.QPushButton("Create")
        self.mode_create_btn.setCheckable(True)
        self.mode_create_btn.setChecked(True)
        self.mode_create_btn.setMinimumWidth(80)
        dark_mode.style_mode_button(self.mode_create_btn)
        self.mode_create_btn.clicked.connect(lambda: self._switch_mode("create"))
        mode_layout.addWidget(self.mode_create_btn)
        
        self.mode_update_btn = QtWidgets.QPushButton("Update")
        self.mode_update_btn.setCheckable(True)
        self.mode_update_btn.setMinimumWidth(80)
        dark_mode.style_mode_button(self.mode_update_btn)
        self.mode_update_btn.clicked.connect(lambda: self._switch_mode("update"))
        mode_layout.addWidget(self.mode_update_btn)
        
        self.mode_delete_btn = QtWidgets.QPushButton("Delete")
        self.mode_delete_btn.setCheckable(True)
        self.mode_delete_btn.setMinimumWidth(80)
        dark_mode.style_mode_button(self.mode_delete_btn, is_delete=True)
        self.mode_delete_btn.clicked.connect(lambda: self._switch_mode("delete"))
        mode_layout.addWidget(self.mode_delete_btn)
        
        self.mode_import_btn = QtWidgets.QPushButton("Import")
        self.mode_import_btn.setCheckable(True)
        self.mode_import_btn.setMinimumWidth(80)
        dark_mode.style_mode_button(self.mode_import_btn)
        self.mode_import_btn.clicked.connect(lambda: self._switch_mode("import"))
        mode_layout.addWidget(self.mode_import_btn)
        
        mode_layout.addStretch()
        self.mode_frame.layout().addStretch()
        layout.addWidget(self.mode_frame, 0, 0, 1, 4)

        # Row 1: Batch selector (for update/delete modes)
        batch_selector_frame = QtWidgets.QFrame()
        batch_selector_layout = QtWidgets.QVBoxLayout()
        batch_selector_layout.setContentsMargins(0, 0, 0, 0)
        batch_selector_layout.setSpacing(4)
        batch_selector_frame.setLayout(batch_selector_layout)
        
        self.batch_selector_btn = QtWidgets.QPushButton("Select Batch...")
        self.batch_selector_btn.setMaximumWidth(200)
        self.batch_selector_btn.clicked.connect(self._open_batch_selector)
        self.batch_selector_btn.setVisible(False)
        batch_selector_layout.addWidget(self.batch_selector_btn)
        
        # Summary label for selected batch
        self.batch_summary_label = QtWidgets.QLabel("")
        dark_mode.style_batch_summary_label(self.batch_summary_label)
        self.batch_summary_label.setWordWrap(True)
        self.batch_summary_label.setVisible(False)
        batch_selector_layout.addWidget(self.batch_summary_label)
        batch_selector_layout.addStretch()
        
        layout.addWidget(batch_selector_frame, 1, 0, 1, 4)

        # Row 2
        event_name_label = QtWidgets.QLabel("Event Name")
        event_name_label.setToolTip("Name that will appear in your calendar")
        layout.addWidget(event_name_label, 2, 0)
        self.event_name = QtWidgets.QLineEdit()
        self.event_name.setToolTip("Name that will appear in your calendar")
        layout.addWidget(self.event_name, 2, 1)

        notification_email_label = QtWidgets.QLabel("Notification Email")
        notification_email_label.setToolTip("Email address to receive notifications about this event (optional)")
        layout.addWidget(notification_email_label, 2, 2)
        self.notification_email = QtWidgets.QLineEdit()
        self.notification_email.setToolTip("Email address to receive notifications about this event (optional)")
        layout.addWidget(self.notification_email, 2, 3)

        # Row 3
        start_date_label = QtWidgets.QLabel("Start Date")
        start_date_label.setToolTip("First day of your vacation")
        layout.addWidget(start_date_label, 3, 0)
        self.start_date = DatePicker()
        self.start_date.setToolTip("First day of your vacation")
        layout.addWidget(self.start_date, 3, 1)

        # Time picker spinners and preset (no separate start_time QTimeEdit to avoid modal)
        self._build_time_picker(layout)

        # Row 4
        end_date_label = QtWidgets.QLabel("End Date")
        end_date_label.setToolTip("Last day of your vacation (inclusive)")
        layout.addWidget(end_date_label, 4, 0)
        self.end_date = DatePicker()
        self.end_date.setToolTip("Last day of your vacation (inclusive)")
        layout.addWidget(self.end_date, 4, 1)

        # Day length spinners (no separate QTimeEdit to avoid modal)

        # Row 5 Weekdays
        self.weekday_boxes: dict[str, QtWidgets.QCheckBox] = {}
        weekday_frame = QtWidgets.QFrame()
        weekday_layout = QtWidgets.QHBoxLayout()
        weekday_frame.setLayout(weekday_layout)
        for key, label in (
            ("monday", "MO"),
            ("tuesday", "TU"),
            ("wednesday", "WE"),
            ("thursday", "TH"),
            ("friday", "FR"),
            ("saturday", "SA"),
            ("sunday", "SU"),
        ):
            box = QtWidgets.QCheckBox(label)
            box.setToolTip(f"Include {label.capitalize()} in vacation period")
            self.weekday_boxes[key] = box
            weekday_layout.addWidget(box)
        weekday_label = QtWidgets.QLabel("Weekdays")
        weekday_label.setToolTip("Select which days of the week are part of your vacation")
        layout.addWidget(weekday_label, 5, 0)
        layout.addWidget(weekday_frame, 5, 1)

        self.days_label = QtWidgets.QLabel("check settings")
        self.days_label.setToolTip("Days remaining after your vacation ends or '--' if already past")
        layout.addWidget(self.days_label, 5, 2, 1, 2)

        # Row 6 calendar select + buttons
        self.process_button = QtWidgets.QPushButton("Insert Into Calendar")
        self.process_button.setToolTip("Create vacation events in the selected calendar (Ctrl+Enter to execute)")
        self.process_button.clicked.connect(self._process)
        self.process_button.setMinimumHeight(32)
        layout.addWidget(self.process_button, 6, 0, 1, 2)

        # Undo button for most recent batch
        self.undo_button = QtWidgets.QPushButton("Undo Last Batch")
        self.undo_button.setToolTip("Remove the most recently added events (Ctrl+Z)")
        self.undo_button.clicked.connect(self._undo)
        self.undo_button.setEnabled(False)
        layout.addWidget(self.undo_button, 6, 2, 1, 1)

        # Redo button for most recent undone batch
        self.redo_button = QtWidgets.QPushButton("Redo Last Batch")
        self.redo_button.setToolTip("Restore the most recently undone events (Ctrl+Y)")
        self.redo_button.clicked.connect(self._redo)
        self.redo_button.setEnabled(False)
        layout.addWidget(self.redo_button, 6, 3, 1, 1)

        # Undelete button for deleted batches
        self.undelete_button = QtWidgets.QPushButton("Restore Deleted")
        self.undelete_button.setToolTip("Restore any of the deleted event batches")
        self.undelete_button.clicked.connect(self._open_undelete_selector)
        self.undelete_button.setEnabled(False)
        layout.addWidget(self.undelete_button, 7, 0, 1, 1)

        # Validation status label - shows why button is disabled
        self.validation_status = QtWidgets.QLabel("")
        dark_mode.style_validation_status(self.validation_status)
        self.validation_status.setWordWrap(True)
        layout.addWidget(self.validation_status, 7, 1, 1, 3)

        self.send_email_checkbox = QtWidgets.QCheckBox("Send notification email")
        self.send_email_checkbox.setToolTip("Send an email to the notification address when events are created")
        layout.addWidget(self.send_email_checkbox, 8, 0, 1, 2)

        # Calendar selector
        calendar_label = QtWidgets.QLabel("Calendar:")
        calendar_label.setStyleSheet("font-weight: bold; color: #0288d1;")
        layout.addWidget(calendar_label, 8, 2)
        
        self.calendar_combo = QtWidgets.QComboBox()
        self.calendar_combo.setToolTip("Select which Google Calendar to use for events")
        self.calendar_combo.addItem("Loading...")
        self.calendar_combo.setEnabled(False)
        self.calendar_combo.currentTextChanged.connect(self._on_calendar_changed)
        layout.addWidget(self.calendar_combo, 8, 3)

        # Import mode controls (hidden unless Import mode)
        self.import_controls_frame = QtWidgets.QFrame()
        self.import_controls_frame.setVisible(False)
        dark_mode.style_import_panel(self.import_controls_frame)
        self.import_controls_frame.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self.import_controls_frame.setMinimumHeight(220)
        import_layout = QtWidgets.QVBoxLayout()
        import_layout.setContentsMargins(0, 0, 0, 0)
        import_layout.setSpacing(6)
        self.import_controls_frame.setLayout(import_layout)

        import_instructions = QtWidgets.QLabel("Import existing calendar events and group them into batches. Use the date range below, fetch, then select the batches to import.")
        import_instructions.setWordWrap(True)
        import_layout.addWidget(import_instructions)

        import_dates_layout = QtWidgets.QHBoxLayout()
        import_dates_layout.setSpacing(8)
        import_dates_layout.addWidget(QtWidgets.QLabel("From:"))
        self.import_start_date = DatePicker()
        self.import_start_date.setDate(QtCore.QDate.currentDate().addMonths(-3))
        self.import_start_date.dateChanged.connect(self._update_validation)
        import_dates_layout.addWidget(self.import_start_date)

        import_dates_layout.addWidget(QtWidgets.QLabel("To:"))
        self.import_end_date = DatePicker()
        self.import_end_date.setDate(QtCore.QDate.currentDate().addMonths(3))
        self.import_end_date.dateChanged.connect(self._update_validation)
        import_dates_layout.addWidget(self.import_end_date)
        import_dates_layout.addStretch()
        import_layout.addLayout(import_dates_layout)

        import_actions_layout = QtWidgets.QHBoxLayout()
        self.import_fetch_button = QtWidgets.QPushButton("Fetch from Calendar")
        self.import_fetch_button.setToolTip("Fetch events in the selected date range and group them into batches")
        dark_mode.style_import_button(self.import_fetch_button)
        self.import_fetch_button.clicked.connect(self._start_import_fetch)
        import_actions_layout.addWidget(self.import_fetch_button)
        self.import_status_label = QtWidgets.QLabel("Idle")
        dark_mode.style_import_label(self.import_status_label)
        import_actions_layout.addWidget(self.import_status_label)
        import_actions_layout.addStretch()
        import_layout.addLayout(import_actions_layout)

        self.import_list = QtWidgets.QListWidget()
        dark_mode.style_import_list(self.import_list)
        self.import_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.import_list.setMinimumHeight(180)
        self.import_list.itemChanged.connect(self._update_validation)
        import_layout.addWidget(self.import_list)

        import_select_layout = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: [self.import_list.item(i).setCheckState(QtCore.Qt.Checked) for i in range(self.import_list.count())])
        import_select_layout.addWidget(select_all_btn)
        deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: [self.import_list.item(i).setCheckState(QtCore.Qt.Unchecked) for i in range(self.import_list.count())])
        import_select_layout.addWidget(deselect_all_btn)
        import_select_layout.addStretch()
        import_layout.addLayout(import_select_layout)

        layout.addWidget(self.import_controls_frame, 9, 0, 1, 4)

        # Log area with header
        log_header_layout = QtWidgets.QHBoxLayout()
        log_header_layout.addWidget(QtWidgets.QLabel("Activity Log"))
        log_header_layout.addStretch()
        clear_log_button = QtWidgets.QPushButton("Clear")
        clear_log_button.setMaximumWidth(80)
        clear_log_button.setToolTip("Clear all log messages")
        clear_log_button.clicked.connect(self._clear_log)
        log_header_layout.addWidget(clear_log_button)
        
        log_container = QtWidgets.QWidget()
        log_container_layout = QtWidgets.QVBoxLayout()
        log_container_layout.setContentsMargins(0, 0, 0, 0)
        log_container.setLayout(log_container_layout)
        
        log_container_layout.addLayout(log_header_layout)
        
        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background-color: #f5f5f5; color: #333; font-family: monospace; font-size: 10px;")
        self.log_box.setMaximumHeight(150)
        log_container_layout.addWidget(self.log_box)
        
        layout.addWidget(log_container, 10, 0, 1, 4)

        self.setCentralWidget(central)

        # Import mode state
        self.import_batches: list[dict] = []
        self.import_thread: QtCore.QThread | None = None
        self.import_worker: QtCore.QObject | None = None
        self.import_fetch_in_progress: bool = False

        for widget in (
            self.event_name,
            self.notification_email,
            self.start_date,
            self.end_date,
            *self.weekday_boxes.values(),
            self.send_email_checkbox,
            self.calendar_combo,
        ):
            if isinstance(widget, DatePicker):
                widget.dateChanged.connect(self._on_date_changed)
            elif isinstance(widget, QtWidgets.QAbstractButton):
                widget.toggled.connect(self._update_validation)
            elif isinstance(widget, QtWidgets.QLineEdit):
                widget.textChanged.connect(self._update_validation)
            elif isinstance(widget, (QtWidgets.QTimeEdit, QtWidgets.QTimeEdit)):
                widget.timeChanged.connect(self._update_validation)
            elif isinstance(widget, QtWidgets.QComboBox):
                widget.currentIndexChanged.connect(self._update_validation)

        # Set up keyboard shortcuts
        undo_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Undo, self)
        undo_shortcut.activated.connect(self._undo)
        
        redo_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Redo, self)
        redo_shortcut.activated.connect(self._redo)
        
        # Ctrl+Enter to process
        process_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL | QtCore.Qt.Key_Return), self)
        process_shortcut.activated.connect(self._process)

    def _setup_status_bar(self) -> None:
        """Set up the status bar with progress indicator and permanent widgets."""
        status_bar = self.statusBar()

        # Progress bar for operations
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)  # Hide by default
        self.progress_bar.setMaximumWidth(200)
        status_bar.addPermanentWidget(self.progress_bar)

        # Permanent status widget for undo history
        self.undo_status_label = QtWidgets.QLabel("No undo history")
        self.undo_status_label.setToolTip(
            "Shows the number of batches available to undo"
        )
        status_bar.addPermanentWidget(self.undo_status_label)

        # Initial status message
        status_bar.showMessage("Ready")

    def _apply_settings(self) -> None:
        self.notification_email.setText(self.settings.email_address)
        self.event_name.setText("")
        # Set start time spinners to 08:00
        self.hour_spinbox.setValue(8)
        self.minute_spinbox.setValue(0)
        # Set day length spinners to 08:00
        self.day_length_hour_spinbox.setValue(8)
        self.day_length_minute_spinbox.setValue(0)
        self.send_email_checkbox.setChecked(self.settings.send_email)

        for key, box in self.weekday_boxes.items():
            box.setChecked(self.settings.weekdays.get(key, True))

        # set dates default to today
        today = QtCore.QDate.currentDate()
        self.start_date.setDate(today)
        self.end_date.setDate(today)

        # Update calendar combo with current calendar
        if self.settings.calendar in self.calendar_names:
            self.calendar_combo.setCurrentText(self.settings.calendar)
        elif self.calendar_names:
            self.calendar_combo.setCurrentIndex(0)

        self.undo_button.setEnabled(False)

    def _on_date_changed(self, _qdate: QtCore.QDate) -> None:
        """Keep start/end dates in chronological order when either changes."""
        start = self.start_date.date()
        end = self.end_date.date()
        # Normalize keeping the date the user just edited as the source of truth
        if start.isValid() and end.isValid():
            sender = self.sender()

            if sender is self.start_date and start > end:
                # User moved the start later than the end -> pull end forward
                self.end_date.blockSignals(True)
                self.end_date.setDate(start)
                self.end_date.blockSignals(False)
                end = start
            elif sender is self.end_date and end < start:
                # User moved the end earlier than the start -> push start back
                self.start_date.blockSignals(True)
                self.start_date.setDate(end)
                self.start_date.blockSignals(False)
                start = end
            elif start > end:
                # Fallback for programmatic changes: align end to start
                self.end_date.blockSignals(True)
                self.end_date.setDate(start)
                self.end_date.blockSignals(False)
                end = start
        self._update_validation()

    def _build_time_picker(self, layout: QtWidgets.QGridLayout) -> None:
        """Add spinners for hour/minute and a combobox with preset times."""
        container = QtWidgets.QWidget()
        hbox = QtWidgets.QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        container.setLayout(hbox)

        # Hour spinner
        self.hour_spinbox = QtWidgets.QSpinBox()
        self.hour_spinbox.setMinimum(0)
        self.hour_spinbox.setMaximum(23)
        self.hour_spinbox.setValue(8)
        self.hour_spinbox.setMaximumWidth(60)
        self.hour_spinbox.setPrefix("h: ")
        self.hour_spinbox.setToolTip("Start hour (0-23)")
        self.hour_spinbox.valueChanged.connect(self._on_time_spinners_changed)
        hbox.addWidget(self.hour_spinbox)

        # Minute spinner
        self.minute_spinbox = QtWidgets.QSpinBox()
        self.minute_spinbox.setMinimum(0)
        self.minute_spinbox.setMaximum(59)
        self.minute_spinbox.setValue(0)
        self.minute_spinbox.setMaximumWidth(60)
        self.minute_spinbox.setPrefix("m: ")
        self.minute_spinbox.setToolTip("Start minute (0-59)")
        self.minute_spinbox.valueChanged.connect(self._on_time_spinners_changed)
        hbox.addWidget(self.minute_spinbox)

        # Preset times dropdown
        self.time_preset_combo = QtWidgets.QComboBox()
        self.time_preset_combo.setMaximumWidth(110)
        self.time_preset_combo.setToolTip("Quick select common work start times")
        self.time_preset_combo.addItem("8:00", 8 * 3600)
        self.time_preset_combo.addItem("9:00", 9 * 3600)
        self.time_preset_combo.addItem("12:00", 12 * 3600)
        self.time_preset_combo.addItem("13:00", 13 * 3600)
        self.time_preset_combo.addItem("14:00", 14 * 3600)
        self.time_preset_combo.addItem("17:00", 17 * 3600)
        self.time_preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        hbox.addWidget(self.time_preset_combo)

        start_time_label = QtWidgets.QLabel("Start Time")
        start_time_label.setToolTip("Time when your work day begins")
        layout.addWidget(start_time_label, 3, 2)
        layout.addWidget(container, 3, 3)

        # Day length spinners (Row 4, Col 2-3)
        day_length_label = QtWidgets.QLabel("Day Length")
        day_length_label.setToolTip("How many hours/minutes you work per day")
        layout.addWidget(day_length_label, 4, 2)
        day_length_container = QtWidgets.QWidget()
        day_length_hbox = QtWidgets.QHBoxLayout()
        day_length_hbox.setContentsMargins(0, 0, 0, 0)
        day_length_hbox.setSpacing(4)
        day_length_container.setLayout(day_length_hbox)

        # Day length hour spinner
        self.day_length_hour_spinbox = QtWidgets.QSpinBox()
        self.day_length_hour_spinbox.setMinimum(0)
        self.day_length_hour_spinbox.setMaximum(23)
        self.day_length_hour_spinbox.setValue(8)
        self.day_length_hour_spinbox.setMaximumWidth(60)
        self.day_length_hour_spinbox.setPrefix("h: ")
        self.day_length_hour_spinbox.setToolTip("Work day hours (0-23)")
        self.day_length_hour_spinbox.valueChanged.connect(self._update_validation)
        day_length_hbox.addWidget(self.day_length_hour_spinbox)

        # Day length minute spinner
        self.day_length_minute_spinbox = QtWidgets.QSpinBox()
        self.day_length_minute_spinbox.setMinimum(0)
        self.day_length_minute_spinbox.setMaximum(59)
        self.day_length_minute_spinbox.setValue(0)
        self.day_length_minute_spinbox.setMaximumWidth(60)
        self.day_length_minute_spinbox.setPrefix("m: ")
        self.day_length_minute_spinbox.setToolTip("Work day minutes (0-59)")
        self.day_length_minute_spinbox.valueChanged.connect(self._update_validation)
        day_length_hbox.addWidget(self.day_length_minute_spinbox)
        day_length_hbox.addStretch()

        layout.addWidget(day_length_container, 4, 3)

    def _on_time_spinners_changed(self) -> None:
        """Update validation when time spinners change."""
        self._update_validation()

    def _on_preset_selected(self) -> None:
        """Handle preset selection - update spinners."""
        data = self.time_preset_combo.currentData()
        if data is not None:
            seconds = data
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            self.hour_spinbox.blockSignals(True)
            self.minute_spinbox.blockSignals(True)
            self.hour_spinbox.setValue(hours)
            self.minute_spinbox.setValue(minutes)
            self.hour_spinbox.blockSignals(False)
            self.minute_spinbox.blockSignals(False)
            self._update_validation()

    def _get_current_calendar(self) -> str:
        """Get the currently selected calendar from the combo box."""
        text = self.calendar_combo.currentText()
        return text if text else ""

    def _current_weekdays(self) -> dict[str, bool]:
        return {key: box.isChecked() for key, box in self.weekday_boxes.items()}

    def _collect_request(self) -> ScheduleRequest | None:
        try:
            start_date = parse_date(self.start_date.date())
            end_date = parse_date(self.end_date.date())
            # Use spinners for start time (no modal time edit)
            start_time_obj = QtCore.QTime(self.hour_spinbox.value(), self.minute_spinbox.value())
            start_time = parse_time(start_time_obj)
        except Exception:
            return None
        # Use spinners for day length
        day_length_hours = self.day_length_hour_spinbox.value() + (self.day_length_minute_spinbox.value() / 60.0)

        return ScheduleRequest(
            event_name=self.event_name.text(),
            notification_email=self.notification_email.text(),
            calendar_name=self._get_current_calendar(),
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            day_length_hours=day_length_hours,
            weekdays=self._current_weekdays(),
            send_email=self.send_email_checkbox.isChecked(),
        )

    def _update_validation(self) -> None:
        # Validation logic differs by mode
        if self.current_mode == "create":
            self._update_validation_create()
        elif self.current_mode == "update":
            self._update_validation_update()
        elif self.current_mode == "delete":
            self._update_validation_delete()
        elif self.current_mode == "import":
            self._update_validation_import()

    def _update_validation_create(self) -> None:
        """Validate create mode inputs."""
        request = self._collect_request()
        validation_errors: list[str] = []
        if request:
            validation_errors = validate_request(request)
        else:
            validation_errors = ["Complete required fields"]
        # Update validation status label with error messages (one per line for clarity)
        if validation_errors:
            # Show errors with bullet points on separate lines for readability
            error_text = "⚠ " + "\n  ".join(validation_errors)
            self.validation_status.setText(error_text)
        else:
            self.validation_status.setText("")

        if not validation_errors and request:
            schedule = build_schedule(request)
            days = len(schedule)
            hours = days * request.day_length_hours
            self.days_label.setText(f"{days} days ({hours:.2f} hours)")
        else:
            self.days_label.setText("check settings")

        self.process_button.setEnabled(
            len(validation_errors) == 0 and not self._creation_running()
        )
        self.undo_button.setEnabled(
            self.undo_manager.can_undo()
            and not self._creation_running()
            and not self._undo_running()
        )

    def _update_validation_update(self) -> None:
        """Validate update mode inputs."""
        request = self._collect_request()
        validation_errors: list[str] = []
        if request:
            validation_errors = validate_request(request)
        else:
            validation_errors = ["Complete required fields"]
        
        if not self.selected_batch_for_operation:
            validation_errors.append("Select a batch to update")

        # Update validation status label with error messages (one per line for clarity)
        if validation_errors:
            error_text = "⚠ " + "\n  ".join(validation_errors)
            self.validation_status.setText(error_text)
        else:
            self.validation_status.setText("")

        if not validation_errors and request:
            schedule = build_schedule(request)
            days = len(schedule)
            hours = days * request.day_length_hours
            self.days_label.setText(f"{days} days ({hours:.2f} hours)")
        else:
            self.days_label.setText("check settings")

        self.process_button.setEnabled(
            len(validation_errors) == 0 and not self._creation_running()
        )
        self.undo_button.setEnabled(
            self.undo_manager.can_undo()
            and not self._creation_running()
            and not self._undo_running()
        )

    def _update_validation_delete(self) -> None:
        """Validate delete mode inputs."""
        validation_errors: list[str] = []
        
        if not self.selected_batch_for_operation:
            validation_errors.append("Select a batch to delete")

        # Update validation status label with error messages (one per line for clarity)
        if validation_errors:
            error_text = "⚠ " + "\n  ".join(validation_errors)
            self.validation_status.setText(error_text)
        else:
            self.validation_status.setText("")

        self.days_label.setText("check settings")

        self.process_button.setEnabled(
            len(validation_errors) == 0 and not self._creation_running()
        )
        self.undo_button.setEnabled(
            self.undo_manager.can_undo()
            and not self._creation_running()
            and not self._undo_running()
        )

    def _update_validation_import(self) -> None:
        """Validate import mode inputs."""
        calendar_name = self.calendar_combo.currentText()
        if not calendar_name or calendar_name == "Loading...":
            self.validation_status.setText("⚠ Please select a calendar")
            self.process_button.setEnabled(False)
            return

        if self.import_fetch_in_progress:
            self.validation_status.setText("Fetching events…")
            self.process_button.setEnabled(False)
            return

        if not self.import_batches:
            self.validation_status.setText("Fetch events to see available batches")
            self.process_button.setEnabled(False)
            return

        selected = self._selected_import_batches()
        if not selected:
            self.validation_status.setText("Select at least one batch to import")
            self.process_button.setEnabled(False)
            return

        self.validation_status.setText("")
        self.process_button.setEnabled(True)

    def _save_settings(self, request: ScheduleRequest) -> None:
        settings = Settings(
            email_address=request.notification_email,
            calendar=request.calendar_name,
            weekdays=self._current_weekdays(),
            send_email=request.send_email,
        )
        self.settings = settings
        self.config_manager.save(settings)

    def _save_settings_to_disk(self) -> None:
        """Save current settings to disk (called on window close or app exit)."""
        current_email = self.notification_email.text()
        current_calendar = self._get_current_calendar()
        current_weekdays = self._current_weekdays()
        current_send_email = self.send_email_checkbox.isChecked()

        settings = Settings(
            email_address=current_email,
            calendar=current_calendar,
            weekdays=current_weekdays,
            send_email=current_send_email,
        )
        self.settings = settings
        self.config_manager.save(settings)

    def _process(self) -> None:
        """Route to the appropriate handler based on current mode."""
        if self.current_mode == "create":
            self._process_create()
        elif self.current_mode == "update":
            self._process_update()
        elif self.current_mode == "delete":
            self._process_delete()
        elif self.current_mode == "import":
            self._import_batches()

    def _switch_mode(self, mode: str) -> None:
        """Switch the active mode and update UI accordingly."""
        # Ensure calendar combo is populated if we have calendar data
        if self.calendar_names and not self.calendar_combo.isEnabled():
            self.calendar_combo.clear()
            self.calendar_combo.addItems(self.calendar_names)
            self.calendar_combo.setEnabled(True)
            if self.settings and self.settings.calendar in self.calendar_names:
                self.calendar_combo.setCurrentText(self.settings.calendar)
            elif self.calendar_names:
                self.calendar_combo.setCurrentIndex(0)

        self.current_mode = mode
        self.selected_batch_for_operation = None  # Reset batch selection
        self.batch_summary_label.setText("")  # Clear summary
        
        # Update button states
        self.mode_create_btn.setChecked(mode == "create")
        self.mode_update_btn.setChecked(mode == "update")
        self.mode_delete_btn.setChecked(mode == "delete")
        self.mode_import_btn.setChecked(mode == "import")
        
        # Default visibility
        self.batch_selector_btn.setVisible(False)
        self.batch_summary_label.setVisible(False)

        if mode == "create":
            self.process_button.setText("Insert Into Calendar")
            self.undelete_button.setVisible(True)
            self._set_form_fields_visible(True, True, True)
            self.import_controls_frame.setVisible(False)
            self.validation_status.setText("Fill in event details and schedule, then click Insert Into Calendar")
        elif mode == "update":
            self.process_button.setText("Update Events")
            self.batch_selector_btn.setVisible(True)
            self.batch_summary_label.setVisible(True)
            self.undelete_button.setVisible(True)
            self._set_form_fields_visible(True, True, True)
            self.import_controls_frame.setVisible(False)
            batches = self.undo_manager.get_undoable_batches()
            if not batches:
                self.batch_summary_label.setText("📭 No batches available. Create events first.")
                self.validation_status.setText("Select a batch to update")
            else:
                self.validation_status.setText("Select a batch and modify settings, then click Update Events")
        elif mode == "delete":
            self.process_button.setText("Delete Events")
            self.batch_selector_btn.setVisible(True)
            self.batch_summary_label.setVisible(True)
            self.undelete_button.setVisible(True)
            self._set_form_fields_visible(False, False, False)
            self.import_controls_frame.setVisible(False)
            batches = self.undo_manager.get_undoable_batches()
            if not batches:
                self.batch_summary_label.setText("📭 No batches available. Create events first.")
                self.validation_status.setText("Select a batch to delete")
            else:
                self.validation_status.setText("Select a batch to delete (you can undo this action)")
        elif mode == "import":
            self.process_button.setText("Import Selected Batches")
            self.batch_selector_btn.setVisible(False)
            self.batch_summary_label.setVisible(False)
            self.undelete_button.setVisible(False)
            self._set_form_fields_visible(False, False, False)
            self.import_controls_frame.setVisible(True)
            self.import_status_label.setText("Idle")
            self._reset_import_list()
            self.validation_status.setText("Fetch events, then select batches to import")

        self._update_validation()

    def _set_form_fields_visible(self, show_name_email: bool, show_dates: bool, show_schedule: bool) -> None:
        """Show/hide form fields based on mode requirements."""
        # Event name and email
        for widget in [self.event_name, self.notification_email]:
            self.event_name.setVisible(show_name_email)
            self.notification_email.setVisible(show_name_email)
        
        # Dates
        for widget in [self.start_date, self.end_date]:
            widget.setVisible(show_dates)
        
        # Schedule info (times, weekdays, day length)
        self.hour_spinbox.setVisible(show_schedule)
        self.minute_spinbox.setVisible(show_schedule)
        self.time_preset_combo.setVisible(show_schedule)
        self.day_length_hour_spinbox.setVisible(show_schedule)
        self.day_length_minute_spinbox.setVisible(show_schedule)
        for box in self.weekday_boxes.values():
            box.setVisible(show_schedule)
        self.days_label.setVisible(show_schedule)

    def _open_batch_selector(self) -> None:
        """Open the calendar-based batch selector dialog."""
        dialog = BatchSelectorDialog(self.undo_manager, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            batch_id = dialog.get_selected_batch_id()
            if batch_id:
                self.selected_batch_for_operation = batch_id
                # Update summary label and fill in event name from selected batch
                batch = self.undo_manager.get_batch_by_id(batch_id)
                if batch:
                    event_count = len(batch.events)
                    date_range = f"{batch.events[0].start_time.date()} to {batch.events[-1].end_time.date()}" if batch.events else ""
                    summary = f"{batch.description} · {event_count} event{'s' if event_count != 1 else ''} · {date_range}"
                    self.batch_summary_label.setText(summary)
                    
                    # Fill in event name from the first event in the batch
                    if batch.events and self.current_mode == "update":
                        self.event_name.setText(batch.events[0].event_name)
                self._update_validation()

    def _process_create(self) -> None:
        if self._creation_running():
            if self.creation_worker:
                self.creation_worker.stop()
            return

        request = self._collect_request()
        if not request:
            QtWidgets.QMessageBox.warning(
                self, "Invalid input", "Please correct the highlighted errors."
            )
            return
        errors_list = validate_request(request)
        if errors_list:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "\n".join(errors_list))
            return
        calendar_id = self.calendar_id_by_name.get(request.calendar_name)
        if not calendar_id:
            QtWidgets.QMessageBox.critical(
                self, "Calendar missing", "Selected calendar ID could not be found."
            )
            return

        self.creation_thread = QtCore.QThread()
        self.creation_worker = EventCreationWorker(self.api, calendar_id, request)
        self.creation_worker.moveToThread(self.creation_thread)
        self.creation_thread.started.connect(self.creation_worker.run)
        self.creation_worker.progress.connect(self._on_creation_progress)
        self.creation_worker.error.connect(self._on_creation_error)
        self.creation_worker.finished.connect(self._on_creation_finished)
        self.creation_worker.stopped.connect(self._on_creation_stopped)
        self.creation_worker.finished.connect(self.creation_thread.quit)
        self.creation_worker.stopped.connect(self.creation_thread.quit)
        self.creation_thread.finished.connect(self.creation_thread.deleteLater)

        self.process_button.setText("Stop Processing")
        self.process_button.setEnabled(True)
        self.undo_button.setEnabled(False)
        self._toggle_inputs(False)

        # Show progress bar
        request = self._collect_request()
        if request:
            schedule = build_schedule(request)
            self._show_progress(len(schedule))
        else:
            self._show_progress(0)

        self.creation_thread.start()

    def _process_update(self) -> None:
        """Update events in a selected batch."""
        if not self.selected_batch_for_operation:
            QtWidgets.QMessageBox.warning(self, "No batch selected", "Please select a batch to update.")
            return
        
        batch = self.undo_manager.get_batch_by_id(self.selected_batch_for_operation)
        if not batch:
            QtWidgets.QMessageBox.warning(self, "Batch not found", "The selected batch could not be found.")
            return
        
        if not batch.events:
            QtWidgets.QMessageBox.warning(self, "No events", "Selected batch has no events.")
            return
        
        request = self._collect_request()
        if not request:
            QtWidgets.QMessageBox.warning(
                self, "Invalid input", "Please correct the highlighted errors."
            )
            return
        errors_list = validate_request(request)
        if errors_list:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "\n".join(errors_list))
            return
        
        # Use calendar_id from the old events (original calendar)
        old_calendar_id = batch.events[0].calendar_id
        if not old_calendar_id:
            QtWidgets.QMessageBox.critical(
                self, "Calendar missing", "Original calendar ID could not be found in the batch."
            )
            return
        
        self.update_thread = QtCore.QThread()
        self.update_worker = UpdateWorker(
            self.api,
            old_calendar_id,
            batch.events,
            request,
            send_email=self.send_email_checkbox.isChecked(),
            notification_email=self.notification_email.text(),
        )
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.progress.connect(self._on_update_progress)
        self.update_worker.error.connect(self._on_update_error)
        self.update_worker.finished.connect(self._on_update_finished)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_thread.finished.connect(self.update_thread.deleteLater)

        self.process_button.setEnabled(False)
        self._toggle_inputs(False)
        
        # Show progress bar
        schedule = build_schedule(request)
        self._show_progress(len(schedule))

        self.update_thread.start()

    def _process_delete(self) -> None:
        """Delete events from a selected batch."""
        if not self.selected_batch_for_operation:
            QtWidgets.QMessageBox.warning(self, "No batch selected", "Please select a batch to delete.")
            return
        
        batch = self.undo_manager.get_batch_by_id(self.selected_batch_for_operation)
        if not batch:
            QtWidgets.QMessageBox.warning(self, "Batch not found", "The selected batch could not be found.")
            return
        
        # Build detailed confirmation message with first/last event dates
        event_count = len(batch.events)
        date_range = ""
        if batch.events:
            first_date = batch.events[0].start_time.date()
            last_date = batch.events[-1].end_time.date()
            if first_date == last_date:
                date_range = f"\nDate: {first_date}"
            else:
                date_range = f"\nDates: {first_date} to {last_date}"
        
        confirmation_msg = (
            f"Delete {event_count} event{'s' if event_count != 1 else ''} from batch:\n"
            f"{batch.description}{date_range}\n\n"
            "⚠️  You can undo this action afterward."
        )
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            confirmation_msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        self.delete_thread = QtCore.QThread()
        self.delete_worker = DeleteWorker(
            self.api,
            batch.events,
            send_email=self.send_email_checkbox.isChecked(),
            notification_email=self.notification_email.text(),
            batch_description=batch.description,
        )
        self.delete_worker.moveToThread(self.delete_thread)
        self.delete_thread.started.connect(self.delete_worker.run)
        self.delete_worker.progress.connect(self._append_log)
        self.delete_worker.error.connect(self._on_delete_error)
        self.delete_worker.finished.connect(self._on_delete_finished)
        self.delete_worker.finished.connect(self.delete_thread.quit)
        self.delete_thread.finished.connect(self.delete_thread.deleteLater)

        self.process_button.setEnabled(False)
        self._toggle_inputs(False)
        
        # Show progress bar
        self._show_progress(len(batch.events))

        self.delete_thread.start()

    def _on_creation_progress(self, message: str) -> None:
        """Handle progress updates from event creation worker."""
        # Update progress bar (approximate progress based on messages)
        current_value = self.progress_bar.value()
        if current_value < self.progress_bar.maximum():
            self._update_progress(current_value + 1)

        # Show status message
        self._show_status(message, 3000)  # Show for 3 seconds

        # Also append to log for detailed tracking
        self._append_log(message)

    def _on_creation_error(self, message: str) -> None:
        self._append_log(f"Error: {message}")
        QtWidgets.QMessageBox.critical(self, "Error", message)
        self._reset_creation_state()

    def _on_creation_finished(self, events: list[EnhancedCreatedEvent]) -> None:
        self.created_events = events
        description = (
            f"{len(events)} events: {events[0].event_name if events else 'Unknown'}"
        )
        # Record as operation for redo capability
        self.undo_manager.add_operation(
            operation_type="create",
            affected_event_ids=[e.event_id for e in events],
            event_snapshots=events,
            description=description,
        )
        # Auto-save immediately to prevent data loss on crashes
        self.undo_manager.save_history(str(self._app_data_dir))
        self._append_log(f"Done. Created {len(events)} events.")
        self._reset_creation_state()
        self._update_undo_ui()

    def _on_creation_stopped(self) -> None:
        self._append_log("Processing stopped.")
        self._reset_creation_state()

    def _undo(self) -> None:
        """Undo the most recent batch of events."""
        if self._undo_running():
            return

        # Pop the most recent operation from undo stack to redo stack
        operation = self.undo_manager.undo()
        if not operation:
            return

        # Get events to undo from the operation
        events_to_undo = operation.event_snapshots

        self.undo_thread = QtCore.QThread()
        self.undo_worker = UndoWorker(
            self.api,
            events_to_undo,
            send_email=self.send_email_checkbox.isChecked(),
            notification_email=self.notification_email.text(),
            batch_description=operation.description,
        )
        self.undo_worker.moveToThread(self.undo_thread)
        self.undo_thread.started.connect(self.undo_worker.run)
        self.undo_worker.progress.connect(self._append_log)
        self.undo_worker.error.connect(self._on_undo_error)
        self.undo_worker.finished.connect(self._on_undo_finished)
        self.undo_worker.finished.connect(self.undo_thread.quit)
        self.undo_thread.finished.connect(self.undo_thread.deleteLater)

        self.undo_button.setEnabled(False)
        self._toggle_inputs(False)
        # Show progress for undo operation
        self._show_progress(len(events_to_undo))
        self.undo_thread.start()

    def _on_undo_finished(self, deleted_event_ids: list[str]) -> None:
        self._append_log(f"Undo complete. Deleted {len(deleted_event_ids)} events.")

        # Auto-save immediately after undo to persist the updated state
        self.undo_manager.save_history(str(self._app_data_dir))

        self.created_events = []
        self._stop_thread(self.undo_thread, self.undo_worker)
        self.undo_thread = None
        self.undo_worker = None
        self._toggle_inputs(True)
        self._update_validation()
        self._update_undo_ui()
        self._hide_progress()

    def _on_undo_error(self, message: str) -> None:
        self._append_log(f"Undo error: {message}")
        QtWidgets.QMessageBox.critical(self, "Undo error", message)
        self._stop_thread(self.undo_thread, self.undo_worker)
        self.undo_thread = None
        self.undo_worker = None
        self._toggle_inputs(True)
        self._update_validation()
        self._hide_progress()

    def _redo(self) -> None:
        """Redo the most recently undone batch of events."""
        if self._redo_running():
            return

        # Pop the most recent operation from redo stack to undo stack
        operation = self.undo_manager.redo()
        if not operation:
            return

        # Get events to redo from the operation
        events_to_redo = operation.event_snapshots

        self.redo_thread = QtCore.QThread()
        self.redo_worker = RedoWorker(
            self.api,
            events_to_redo,
            batch_description=operation.description,
        )
        self.redo_worker.moveToThread(self.redo_thread)
        self.redo_thread.started.connect(self.redo_worker.run)
        self.redo_worker.progress.connect(self._append_log)
        self.redo_worker.error.connect(self._on_redo_error)
        self.redo_worker.finished.connect(self._on_redo_finished)
        self.redo_worker.finished.connect(self.redo_thread.quit)
        self.redo_thread.finished.connect(self.redo_thread.deleteLater)

        self.redo_button.setEnabled(False)
        self._toggle_inputs(False)
        # Show progress for redo operation
        self._show_progress(len(events_to_redo))
        self.redo_thread.start()

    def _on_redo_finished(self, created_event_ids: list[str]) -> None:
        self._append_log(f"Redo complete. Created {len(created_event_ids)} events.")

        # Auto-save immediately after redo to persist the updated state
        self.undo_manager.save_history(str(self._app_data_dir))

        self.created_events = []
        self._stop_thread(self.redo_thread, self.redo_worker)
        self.redo_thread = None
        self.redo_worker = None
        self._toggle_inputs(True)
        self._update_validation()
        self._update_undo_ui()
        self._hide_progress()

    def _on_redo_error(self, message: str) -> None:
        self._append_log(f"Redo error: {message}")
        QtWidgets.QMessageBox.critical(self, "Redo error", message)
        self._stop_thread(self.redo_thread, self.redo_worker)
        self.redo_thread = None
        self.redo_worker = None
        self._toggle_inputs(True)
        self._update_validation()
        self._hide_progress()

    def _on_delete_error(self, message: str) -> None:
        self._append_log(f"Delete error: {message}")
        QtWidgets.QMessageBox.critical(self, "Delete error", message)
        self._stop_thread(self.delete_thread, self.delete_worker)
        self.delete_thread = None
        self.delete_worker = None
        self._toggle_inputs(True)
        self._update_validation()

    def _on_delete_finished(self, deleted_event_ids: list[str], batch_description: str) -> None:
        self._append_log(f"Deletion complete. Deleted {len(deleted_event_ids)} events.")

        if self.delete_worker and hasattr(self.delete_worker, "deleted_snapshots"):
            deleted_snapshots = self.delete_worker.deleted_snapshots

            # Remove the original batch from the visible undo history so it no longer appears
            if self.selected_batch_for_operation:
                self.undo_manager.remove_operation(self.selected_batch_for_operation)

            # Record the delete in the dedicated delete stack (allows undelete)
            self.undo_manager.add_operation(
                operation_type="delete",
                affected_event_ids=deleted_event_ids,
                event_snapshots=deleted_snapshots,
                description=f"Deleted: {batch_description}",
            )
            self.undo_manager.save_history(str(self._app_data_dir))

        self._stop_thread(self.delete_thread, self.delete_worker)
        self.delete_thread = None
        self.delete_worker = None
        self._toggle_inputs(True)
        self._update_validation()
        self._update_undo_ui()
        self._switch_mode("create")

    def _open_undelete_selector(self) -> None:
        """Open dialog to select a deleted batch to restore."""
        deleted_batches = self.undo_manager.get_deleted_batches()
        if not deleted_batches:
            QtWidgets.QMessageBox.information(self, "No Deleted Batches", "There are no deleted batches to restore.")
            return
        
        dialog = DeletedBatchSelectorDialog(self.undo_manager, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            batch_id = dialog.get_selected_batch_id()
            if batch_id:
                self._undelete_batch(batch_id)

    def _undelete_batch(self, batch_id: str) -> None:
        """Undelete a specific deleted batch by moving it back to undo stack.
        
        Args:
            batch_id: The batch ID to restore
        """
        # Find the operation in the delete_stack
        operation = None
        for op in self.undo_manager.delete_stack:
            if op.operation_id == batch_id:
                operation = op
                break
            # Also check if any event has this batch_id
            for snapshot in getattr(op, "event_snapshots", []) or []:
                if getattr(snapshot, "batch_id", None) == batch_id:
                    operation = op
                    break
        
        if not operation:
            QtWidgets.QMessageBox.warning(self, "Batch Not Found", "The selected batch could not be found in delete history.")
            return
        
        # Move from delete_stack to undo_stack
        self.undo_manager.delete_stack.remove(operation)
        # Change operation_type back to "create" since it's being restored
        operation.operation_type = "create"
        self.undo_manager.undo_stack.append(operation)
        
        # Clear redo stacks on new operation (standard UX)
        self.undo_manager.redo_stack.clear()
        self.undo_manager.delete_redo_stack.clear()
        self.undo_manager.redo_stack_cleared.emit()
        
        # Save and update UI
        self.undo_manager.save_history(str(self._app_data_dir))
        self._append_log(f"Restored batch: {operation.description}")
        self._update_undo_ui()

    def _on_update_progress(self, message: str) -> None:
        """Handle progress updates from update worker."""
        current_value = self.progress_bar.value()
        if current_value < self.progress_bar.maximum():
            self._update_progress(current_value + 1)
        self._show_status(message, 3000)
        self._append_log(message)

    def _on_update_error(self, message: str) -> None:
        self._append_log(f"Update error: {message}")
        QtWidgets.QMessageBox.critical(self, "Update error", message)
        self._stop_thread(self.update_thread, self.update_worker)
        self.update_thread = None
        self.update_worker = None
        self._toggle_inputs(True)
        self._update_validation()

    def _on_update_finished(
        self,
        new_events: list[EnhancedCreatedEvent],
        old_event_snapshots: list[EnhancedCreatedEvent],
    ) -> None:
        self._append_log(f"Update complete. Created {len(new_events)} updated events.")
        description = f"{len(new_events)} updated events: {new_events[0].event_name if new_events else 'Unknown'}"
        combined_snapshots = old_event_snapshots + new_events
        
        self.undo_manager.add_operation(
            operation_type="update",
            affected_event_ids=[e.event_id for e in new_events],
            event_snapshots=combined_snapshots,
            description=description,
        )
        self.undo_manager.save_history(str(self._app_data_dir))
        
        self._stop_thread(self.update_thread, self.update_worker)
        self.update_thread = None
        self.update_worker = None
        self._toggle_inputs(True)
        self._update_validation()
        self._update_undo_ui()
        self._switch_mode("create")

    def _append_log(self, message: str) -> None:
        self.log_box.appendPlainText(message)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )

    def _clear_log(self) -> None:
        """Clear all log messages."""
        self.log_box.clear()

    def _on_calendar_changed(self, calendar_name: str) -> None:
        """Handle calendar selection change."""
        if calendar_name and calendar_name != "Loading...":
            # Save the new calendar selection to settings
            self.settings.calendar = calendar_name
            self.config_manager.save(self.settings)
            self._update_validation()
    def _reset_import_list(self) -> None:
        self.import_batches = []
        self.import_list.clear()
        self.import_status_label.setText("Idle")

    def _selected_import_batches(self) -> list[dict]:
        selected: list[dict] = []
        for i in range(self.import_list.count()):
            item = self.import_list.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                idx = item.data(QtCore.Qt.UserRole)
                if isinstance(idx, int) and 0 <= idx < len(self.import_batches):
                    selected.append(self.import_batches[idx])
        return selected

    def _start_import_fetch(self) -> None:
        """Begin fetching events asynchronously and populate the import list."""
        calendar_name = self.calendar_combo.currentText()
        calendar_id = self.calendar_id_by_name.get(calendar_name)
        if not calendar_id:
            QtWidgets.QMessageBox.warning(self, "No Calendar", "Please select a calendar first.")
            return

        start_dt = self.import_start_date.date().toPython()
        end_dt = self.import_end_date.date().toPython()
        if start_dt > end_dt:
            start_dt, end_dt = end_dt, start_dt
            self.import_start_date.setDate(QtCore.QDate(start_dt.year, start_dt.month, start_dt.day))
            self.import_end_date.setDate(QtCore.QDate(end_dt.year, end_dt.month, end_dt.day))

        if self.import_thread and self.import_thread.isRunning():
            return

        self.import_fetch_in_progress = True
        self.import_fetch_button.setEnabled(False)
        self.process_button.setEnabled(False)
        self.import_status_label.setText("Fetching…")
        self.statusBar().showMessage("Scanning calendar…")
        self._append_log("Import: fetching events from calendar…")
        self._reset_import_list()
        self._update_validation()

        self.import_thread = QtCore.QThread()
        self.import_worker = self.ImportFetchWorker(
            self.api,
            calendar_id,
            start_dt,
            end_dt,
            self._group_events_into_batches,
        )
        self.import_worker.moveToThread(self.import_thread)
        self.import_thread.started.connect(self.import_worker.run)
        self.import_worker.finished.connect(self._on_import_fetch_finished)
        self.import_worker.error.connect(self._on_import_fetch_error)
        self.import_worker.finished.connect(self.import_thread.quit)
        self.import_worker.error.connect(self.import_thread.quit)
        self.import_thread.finished.connect(self.import_thread.deleteLater)
        self.import_thread.finished.connect(self._on_import_thread_finished)
        self.import_thread.start()

    def _on_import_fetch_finished(self, batches: list[dict]) -> None:
        self.import_fetch_in_progress = False
        self.import_fetch_button.setEnabled(True)
        self.import_batches = batches
        self.import_list.blockSignals(True)
        self.import_list.clear()
        for i, batch in enumerate(batches):
            item = QtWidgets.QListWidgetItem(
                f"{batch['description']} - {batch['event_count']} event(s)"
            )
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            item.setData(QtCore.Qt.UserRole, i)
            self.import_list.addItem(item)
        self.import_list.blockSignals(False)

        if batches:
            self.import_status_label.setText(f"Found {len(batches)} batch(es)")
        else:
            self.import_status_label.setText("No batches found")

        self.statusBar().showMessage("Ready")
        self._append_log(f"Import: found {len(batches)} batch(es)")

    def _on_import_fetch_error(self, message: str) -> None:
        self.import_fetch_in_progress = False
        self.import_fetch_button.setEnabled(True)
        self.statusBar().showMessage("Ready")
        self.import_status_label.setText("Error")
        self._append_log(f"Import error: {message}")
        QtWidgets.QMessageBox.critical(self, "Import Error", message)

    def _on_import_thread_finished(self) -> None:
        self.import_thread = None
        self.import_worker = None

    def _import_batches(self) -> None:
        """Import the selected batches from the already-fetched list."""
        selected_batches = self._selected_import_batches()
        if not selected_batches:
            QtWidgets.QMessageBox.information(self, "No Batches Selected", "Select at least one batch to import.")
            self._update_validation()
            return

        for batch in selected_batches:
            self.undo_manager.add_operation(
                operation_type="create",
                affected_event_ids=[e.event_id for e in batch["events"]],
                event_snapshots=batch["events"],
                description=batch["description"],
            )

        self.undo_manager.save_history(str(self._app_data_dir))
        self._update_undo_ui()

        self._append_log(f"Imported {len(selected_batches)} batch(es)")
        QtWidgets.QMessageBox.information(
            self,
            "Import Complete",
            f"Successfully imported {len(selected_batches)} batch(es).\n"
            "You can now use Update or Delete modes to modify these events.",
        )
        self._update_validation()
    
    class ImportFetchWorker(QtCore.QObject):
        finished = QtCore.Signal(list)
        error = QtCore.Signal(str)

        def __init__(self, api, calendar_id: str, start_dt: dt.date, end_dt: dt.date, group_func):
            super().__init__()
            self.api = api
            self.calendar_id = calendar_id
            self.start_dt = start_dt
            self.end_dt = end_dt
            self.group_func = group_func

        def run(self) -> None:
            try:
                time_min = dt.datetime.combine(self.start_dt, dt.time.min).isoformat() + "Z"
                time_max = dt.datetime.combine(self.end_dt, dt.time.max).isoformat() + "Z"

                # Prefer calendar_service() helper; fall back to .service for compatibility
                service = getattr(self.api, "service", None)
                if service is None and hasattr(self.api, "calendar_service"):
                    service = self.api.calendar_service()

                if service is None:
                    raise AttributeError("GoogleApi has no calendar service; ensure_connected failed")

                events = service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()

                items = events.get("items", [])
                batches = self.group_func(items, self.calendar_id)
                self.finished.emit(batches)
            except Exception as e:
                self.error.emit(str(e))


    def _group_events_into_batches(self, items: list, calendar_id: str) -> list[dict]:
        """Group calendar events into potential batches based on name and date proximity."""
        # EnhancedCreatedEvent is already imported at module level
        
        # Group events by summary (event name)
        groups: dict[str, list] = {}
        
        for item in items:
            summary = item.get("summary", "Untitled Event")
            event_id = item.get("id")
            
            # Parse start/end times
            start = item.get("start", {})
            end = item.get("end", {})
            
            # Handle both dateTime and date (all-day) events
            if "dateTime" in start:
                start_time = dt.datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
            elif "date" in start:
                start_time = dt.datetime.fromisoformat(start["date"] + "T00:00:00")
            else:
                continue
            
            if "dateTime" in end:
                end_time = dt.datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
            elif "date" in end:
                end_time = dt.datetime.fromisoformat(end["date"] + "T00:00:00")
            else:
                continue
            
            # Create EnhancedCreatedEvent
            enhanced_event = EnhancedCreatedEvent(
                event_id=event_id,
                calendar_id=calendar_id,
                event_name=summary,
                start_time=start_time,
                end_time=end_time,
                created_at=dt.datetime.now(),
                batch_id="",  # Will be set when added to undo manager
                request_snapshot=None
            )
            
            if summary not in groups:
                groups[summary] = []
            groups[summary].append(enhanced_event)
        
        # Convert groups to batches
        batches = []
        for summary, events in groups.items():
            # Sort by start time
            events.sort(key=lambda e: e.start_time)
            
            # Split into sub-batches if there are large gaps (>3 days)
            current_batch = []
            for event in events:
                if not current_batch:
                    current_batch.append(event)
                else:
                    last_event = current_batch[-1]
                    gap_days = (event.start_time.date() - last_event.start_time.date()).days
                    
                    if gap_days <= 3:  # Adjacent or close events
                        current_batch.append(event)
                    else:
                        # Save current batch and start new one
                        if len(current_batch) > 0:
                            batches.append({
                                "description": f"{summary} ({current_batch[0].start_time.date()} - {current_batch[-1].start_time.date()})",
                                "events": current_batch,
                                "event_count": len(current_batch)
                            })
                        current_batch = [event]
            
            # Add final batch
            if current_batch:
                batches.append({
                    "description": f"{summary} ({current_batch[0].start_time.date()} - {current_batch[-1].start_time.date()})",
                    "events": current_batch,
                    "event_count": len(current_batch)
                })
        
        return batches
    
    def _show_batch_import_dialog(self, batches: list[dict]) -> list[dict]:
        """Show dialog for selecting which batches to import."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Batches to Import")
        dialog.setMinimumSize(600, 400)
        
        layout = QtWidgets.QVBoxLayout()
        dialog.setLayout(layout)
        
        label = QtWidgets.QLabel(f"Found {len(batches)} potential batch(es). Select which to import:")
        layout.addWidget(label)
        
        # List widget with checkboxes
        list_widget = QtWidgets.QListWidget()
        list_widget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        
        for i, batch in enumerate(batches):
            item = QtWidgets.QListWidgetItem(
                f"{batch['description']} - {batch['event_count']} event(s)"
            )
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            item.setData(QtCore.Qt.UserRole, i)  # Store batch index
            list_widget.addItem(item)
        
        layout.addWidget(list_widget)
        
        # Select/Deselect all buttons
        button_layout = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.clicked.connect(
            lambda: [list_widget.item(i).setCheckState(QtCore.Qt.Checked) for i in range(list_widget.count())]
        )
        button_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(
            lambda: [list_widget.item(i).setCheckState(QtCore.Qt.Unchecked) for i in range(list_widget.count())]
        )
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Dialog buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return []
        
        # Collect selected batches
        selected = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                batch_idx = item.data(QtCore.Qt.UserRole)
                selected.append(batches[batch_idx])
        
        return selected

    def _reset_creation_state(self) -> None:
        self._toggle_inputs(True)
        self.process_button.setText("Insert Into Calendar")
        self._stop_thread(self.creation_thread, self.creation_worker)
        self.creation_worker = None
        self.creation_thread = None
        self._update_validation()

    def _toggle_inputs(self, enabled: bool) -> None:
        for widget in (
            self.event_name,
            self.notification_email,
            self.start_date,
            self.end_date,
            self.hour_spinbox,
            self.minute_spinbox,
            self.time_preset_combo,
            self.day_length_hour_spinbox,
            self.day_length_minute_spinbox,
            self.send_email_checkbox,
            self.calendar_combo,
            self.import_start_date,
            self.import_end_date,
            self.import_fetch_button,
            self.import_list,
            *self.weekday_boxes.values(),
        ):
            widget.setEnabled(enabled)

    def _creation_running(self) -> bool:
        return bool(self.creation_thread and self.creation_thread.isRunning())

    def _undo_running(self) -> bool:
        return bool(self.undo_thread and self.undo_thread.isRunning())

    def _redo_running(self) -> bool:
        return bool(self.redo_thread and self.redo_thread.isRunning())

    def _update_running(self) -> bool:
        return bool(self.update_thread and self.update_thread.isRunning())

    def _delete_running(self) -> bool:
        return bool(self.delete_thread and self.delete_thread.isRunning())

    @property
    def _operation_in_progress(self) -> bool:
        """Check if any operation is currently in progress."""
        return (
            self._creation_running()
            or self._undo_running()
            or self._redo_running()
            or self._update_running()
            or self._delete_running()
        )

    def _set_operation_in_progress(self, in_progress: bool) -> None:
        """Test helper to force validation refresh."""
        self._update_validation()

    def _stop_thread(
        self, thread: QtCore.QThread | None, worker: object | None
    ) -> None:
        if thread is not None:
            try:
                # Check if thread is still valid and running
                if thread.isRunning():
                    stop_fn = getattr(worker, "stop", None)
                    if callable(stop_fn):
                        stop_fn()
                    thread.quit()
                    thread.wait(3000)
            except RuntimeError:
                # Thread has already been deleted, ignore the error
                pass

    def _stop_all_threads(self) -> None:
        """Stop any running worker threads safely."""
        self._stop_thread(self.creation_thread, self.creation_worker)
        self._stop_thread(self.undo_thread, self.undo_worker)
        self._stop_thread(self.redo_thread, self.redo_worker)
        self._stop_thread(self.update_thread, self.update_worker)
        self._stop_thread(self.delete_thread, self.delete_worker)
        self._stop_thread(self.import_thread, self.import_worker)

    def _update_undo_button_state(self) -> None:
        """Update the undo button state based on available batches."""
        batches = self.undo_manager.get_undoable_batches()
        self.undo_button.setEnabled(
            len(batches) > 0
            and not self._creation_running()
            and not self._undo_running()
            and not self._redo_running()
        )

    def _update_redo_button_state(self) -> None:
        """Update the redo button state based on available batches."""
        batches = self.undo_manager.get_redoable_batches()
        self.redo_button.setEnabled(
            len(batches) > 0
            and not self._creation_running()
            and not self._redo_running()
            and not self._undo_running()
        )

    def _update_undelete_button_state(self) -> None:
        """Update the undelete button state based on deleted batches."""
        deleted_batches = self.undo_manager.get_deleted_batches()
        self.undelete_button.setEnabled(
            len(deleted_batches) > 0
            and not self._creation_running()
            and not self._undo_running()
            and not self._redo_running()
        )

    def _update_undo_ui(self) -> None:
        """Update undo-related UI elements based on current undo state."""
        # Update undo and redo button states
        self._update_undo_button_state()
        self._update_redo_button_state()
        self._update_undelete_button_state()

        # Update status bar undo/redo info
        stats = self.undo_manager.get_history_stats()
        undoable_batches = stats["undoable_batches"]
        undoable_events = stats["undoable_events"]
        redoable_batches = stats["redoable_batches"]
        redoable_events = stats["redoable_events"]
        
        undo_text = f"{undoable_batches} to undo" if undoable_batches > 0 else "0 to undo"
        redo_text = f"{redoable_batches} to redo" if redoable_batches > 0 else "0 to redo"
        self.undo_status_label.setText(f"{undo_text} · {redo_text}")

    def _show_progress(self, maximum: int = 100) -> None:
        """Show and initialize the progress bar."""
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.statusBar().showMessage("Processing...")

    def _update_progress(self, value: int) -> None:
        """Update the progress bar value."""
        self.progress_bar.setValue(value)

    def _hide_progress(self) -> None:
        """Hide the progress bar and clear status."""
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Ready")

    def _show_status(self, message: str, timeout: int = 0) -> None:
        """Show a temporary status message."""
        self.statusBar().showMessage(message, timeout)

    def _on_save_failed(self, error_message: str) -> None:
        """Handle save failure by showing a warning to the user."""
        QtWidgets.QMessageBox.warning(
            self,
            "Save Error",
            f"Failed to save undo history:\\n{error_message}\\n\\nYour calendar events are safe, but undo history may be incomplete.",
        )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
        """Gracefully stop worker threads before the window closes."""

        # Save settings before closing
        self._save_settings_to_disk()

        # Save undo history before stopping threads
        self.undo_manager.save_history(str(self._app_data_dir))

        self._stop_all_threads()

        super().closeEvent(event)

    def __del__(self):
        try:
            self._stop_all_threads()
        except Exception:
            pass


def launch() -> None:
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("VacationCalendarUpdater")
    app.setOrganizationName("dtg01100")
    api = GoogleApi()
    config = ConfigManager()
    window = MainWindow(api, config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch()
