from __future__ import annotations

import sys
from pathlib import Path

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
from ..workers import EventCreationWorker, StartupWorker, UndoWorker, DeleteWorker, UpdateWorker
from .datepicker import DatePicker


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
        self.delete_thread: QtCore.QThread | None = None
        self.update_thread: QtCore.QThread | None = None
        self.creation_worker: EventCreationWorker | None = None
        self.undo_worker: UndoWorker | None = None
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
        self.statusBar().showMessage("Connecting to Google Calendar...")
        self._startup_worker.start()

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

        # Update calendar dropdown
        self.calendar_combo.blockSignals(True)
        self.calendar_combo.clear()
        self.calendar_combo.addItems(calendar_names)

        # Select previously selected calendar or first available
        if self.settings.calendar and self.settings.calendar in calendar_names:
            self.calendar_combo.setCurrentText(self.settings.calendar)
        elif calendar_names:
            self.calendar_combo.setCurrentIndex(0)
        self.calendar_combo.blockSignals(False)

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
            self.calendar_combo.addItem("Primary")
            self.calendar_names = ["Primary"]

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        central.setLayout(layout)

        # Row -1: Mode selector buttons at the very top
        mode_frame = QtWidgets.QFrame()
        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_frame.setLayout(mode_layout)
        
        self.mode_create_btn = QtWidgets.QPushButton("Create")
        self.mode_create_btn.setCheckable(True)
        self.mode_create_btn.setChecked(True)
        self.mode_create_btn.clicked.connect(lambda: self._switch_mode("create"))
        mode_layout.addWidget(self.mode_create_btn)
        
        self.mode_update_btn = QtWidgets.QPushButton("Update")
        self.mode_update_btn.setCheckable(True)
        self.mode_update_btn.clicked.connect(lambda: self._switch_mode("update"))
        mode_layout.addWidget(self.mode_update_btn)
        
        self.mode_delete_btn = QtWidgets.QPushButton("Delete")
        self.mode_delete_btn.setCheckable(True)
        self.mode_delete_btn.clicked.connect(lambda: self._switch_mode("delete"))
        mode_layout.addWidget(self.mode_delete_btn)
        
        mode_layout.addStretch()
        layout.addWidget(mode_frame, 0, 0, 1, 4)

        # Row 1: Batch selector (for update/delete modes)
        self.batch_selector_label = QtWidgets.QLabel("Select Batch:")
        self.batch_selector_label.setVisible(False)
        layout.addWidget(self.batch_selector_label, 1, 0)
        
        self.batch_selector_combo = QtWidgets.QComboBox()
        self.batch_selector_combo.setMinimumWidth(200)
        self.batch_selector_combo.setPlaceholderText("Pick a batch to modify...")
        self.batch_selector_combo.currentIndexChanged.connect(self._on_batch_selected)
        self.batch_selector_combo.setVisible(False)
        layout.addWidget(self.batch_selector_combo, 1, 1)

        # Row 2
        layout.addWidget(QtWidgets.QLabel("Event Name"), 2, 0)
        self.event_name = QtWidgets.QLineEdit()
        layout.addWidget(self.event_name, 2, 1)

        layout.addWidget(QtWidgets.QLabel("Notification Email"), 2, 2)
        self.notification_email = QtWidgets.QLineEdit()
        layout.addWidget(self.notification_email, 2, 3)

        # Row 3
        layout.addWidget(QtWidgets.QLabel("Start Date"), 3, 0)
        self.start_date = DatePicker()
        layout.addWidget(self.start_date, 3, 1)

        layout.addWidget(QtWidgets.QLabel("Start Time"), 3, 2)
        self.start_time = QtWidgets.QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        self.start_time.setMinimumWidth(90)
        self._build_time_picker(layout)

        # Row 4
        layout.addWidget(QtWidgets.QLabel("End Date"), 4, 0)
        self.end_date = DatePicker()
        layout.addWidget(self.end_date, 4, 1)

        layout.addWidget(QtWidgets.QLabel("Day Length"), 4, 2)
        self.day_length = QtWidgets.QTimeEdit()
        self.day_length.setDisplayFormat("HH:mm")
        self.day_length.setMaximumWidth(90)
        self.day_length.setTime(QtCore.QTime(8, 0))
        self.day_length.setToolTip("Length of each day (HH:mm)")
        layout.addWidget(self.day_length, 4, 3)

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
            self.weekday_boxes[key] = box
            weekday_layout.addWidget(box)
        layout.addWidget(weekday_frame, 5, 0, 1, 2)

        self.days_label = QtWidgets.QLabel("check settings")
        layout.addWidget(self.days_label, 5, 2, 1, 2)

        # Row 6 calendar select + buttons
        self.process_button = QtWidgets.QPushButton("Insert Into Calendar")
        self.process_button.clicked.connect(self._process)
        layout.addWidget(self.process_button, 6, 0, 1, 2)

        # Validation status label - shows why button is disabled (moved below undo widgets to avoid overlap)
        self.validation_status = QtWidgets.QLabel("")
        self.validation_status.setStyleSheet("color: #d32f2f; font-size: 11px;")
        self.validation_status.setWordWrap(True)
        layout.addWidget(self.validation_status, 7, 0, 1, 4)

        # Create undo combo box for selective undo
        self.undo_combo = QtWidgets.QComboBox()
        self.undo_combo.setMinimumWidth(200)
        self.undo_combo.setPlaceholderText("Select action to undo...")
        self.undo_combo.currentIndexChanged.connect(self._update_undo_button_state)
        layout.addWidget(self.undo_combo, 6, 2, 1, 1)

        self.undo_button = QtWidgets.QPushButton("Undo Selected")
        self.undo_button.clicked.connect(self._undo)
        self.undo_button.setEnabled(False)
        layout.addWidget(self.undo_button, 6, 3, 1, 1)

        self.send_email_checkbox = QtWidgets.QCheckBox("Send notification email")
        layout.addWidget(self.send_email_checkbox, 8, 0, 1, 2)

        self.calendar_combo = QtWidgets.QComboBox()
        self.calendar_combo.addItems(self.calendar_names)
        layout.addWidget(self.calendar_combo, 8, 2, 1, 2)

        # Log area
        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box, 9, 0, 1, 4)

        self.setCentralWidget(central)

        for widget in (
            self.event_name,
            self.notification_email,
            self.start_date,
            self.end_date,
            self.start_time,
            self.day_length,
            *self.weekday_boxes.values(),
            self.calendar_combo,
            self.send_email_checkbox,
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
        self.start_time.setTime(QtCore.QTime.fromString("0800", "HHmm"))
        self.day_length.setTime(QtCore.QTime(8, 0))
        self.send_email_checkbox.setChecked(self.settings.send_email)

        for key, box in self.weekday_boxes.items():
            box.setChecked(self.settings.weekdays.get(key, True))

        # set dates default to today
        today = QtCore.QDate.currentDate()
        self.start_date.setDate(today)
        self.end_date.setDate(today)

        # calendar selection - block signals to avoid triggering _update_validation
        self.calendar_combo.blockSignals(True)
        if self.settings.calendar in self.calendar_names:
            self.calendar_combo.setCurrentText(self.settings.calendar)
        elif self.calendar_names:
            self.calendar_combo.setCurrentIndex(0)
        self.calendar_combo.blockSignals(False)

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
        """Add a time edit with a drop-down of common times."""

        container = QtWidgets.QWidget()
        hbox = QtWidgets.QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        container.setLayout(hbox)

        time_button = QtWidgets.QToolButton()
        icon = self.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_BrowserReload
        )
        if icon.isNull():
            time_button.setText("⋯")
        else:
            time_button.setIcon(icon)
        time_button.setToolTip("Pick a common start time")
        time_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)

        menu = QtWidgets.QMenu(time_button)
        self._populate_time_menu(menu)
        time_button.setMenu(menu)

        hbox.addWidget(self.start_time)
        hbox.addWidget(time_button)

        layout.addWidget(container, 1, 3)

    def _populate_time_menu(self, menu: QtWidgets.QMenu) -> None:
        menu.clear()
        for hour in range(6, 20):  # 06:00 to 19:45
            for minute in (0, 15, 30, 45):
                t = QtCore.QTime(hour, minute)
                action = menu.addAction(t.toString("HH:mm"))
                action.triggered.connect(
                    lambda _checked=False, tt=t: self.start_time.setTime(tt)
                )

    def _current_weekdays(self) -> dict[str, bool]:
        return {key: box.isChecked() for key, box in self.weekday_boxes.items()}

    def _collect_request(self) -> ScheduleRequest | None:
        try:
            start_date = parse_date(self.start_date.date())
            end_date = parse_date(self.end_date.date())
            start_time = parse_time(self.start_time.time())
        except Exception:
            return None
        day_len_qtime = self.day_length.time()
        day_length_hours = day_len_qtime.hour() + (day_len_qtime.minute() / 60.0)

        return ScheduleRequest(
            event_name=self.event_name.text(),
            notification_email=self.notification_email.text(),
            calendar_name=self.calendar_combo.currentText(),
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

    def _update_validation_create(self) -> None:
        """Validate create mode inputs."""
        request = self._collect_request()
        validation_errors: list[str] = []
        if request:
            validation_errors = validate_request(request)
        else:
            validation_errors = ["Complete required fields"]

        # Update validation status label with error messages
        if validation_errors:
            self.validation_status.setText(" | ".join(validation_errors))
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

        # Update validation status label with error messages
        if validation_errors:
            self.validation_status.setText(" | ".join(validation_errors))
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

        # Update validation status label with error messages
        if validation_errors:
            self.validation_status.setText(" | ".join(validation_errors))
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
        current_calendar = self.calendar_combo.currentText()
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

    def _switch_mode(self, mode: str) -> None:
        """Switch the active mode and update UI accordingly."""
        self.current_mode = mode
        
        # Update button states
        self.mode_create_btn.setChecked(mode == "create")
        self.mode_update_btn.setChecked(mode == "update")
        self.mode_delete_btn.setChecked(mode == "delete")
        
        # Update process button label
        if mode == "create":
            self.process_button.setText("Insert Into Calendar")
            self.batch_selector_label.setVisible(False)
            self.batch_selector_combo.setVisible(False)
            # Show all form fields
            self._set_form_fields_visible(True, True, True)
        elif mode == "update":
            self.process_button.setText("Update Events")
            self.batch_selector_label.setVisible(True)
            self.batch_selector_combo.setVisible(True)
            # Show all form fields
            self._set_form_fields_visible(True, True, True)
            self._update_batch_selector()
        elif mode == "delete":
            self.process_button.setText("Delete Events")
            self.batch_selector_label.setVisible(True)
            self.batch_selector_combo.setVisible(True)
            # Hide most form fields for delete mode, just show batch selector
            self._set_form_fields_visible(False, False, False)
            self._update_batch_selector()
        
        self._update_validation()

    def _set_form_fields_visible(self, show_name_email: bool, show_dates: bool, show_schedule: bool) -> None:
        """Show/hide form fields based on mode requirements."""
        # Event name and email
        for widget in [self.event_name, self.notification_email]:
            if hasattr(self, 'event_name'):
                self.event_name.setVisible(show_name_email)
                self.notification_email.setVisible(show_name_email)
        
        # Dates
        for widget in [self.start_date, self.end_date]:
            widget.setVisible(show_dates)
        
        # Schedule info (times, weekdays, day length)
        self.start_time.setVisible(show_schedule)
        self.day_length.setVisible(show_schedule)
        for box in self.weekday_boxes.values():
            box.setVisible(show_schedule)
        self.days_label.setVisible(show_schedule)

    def _update_batch_selector(self) -> None:
        """Populate the batch selector combo with available batches."""
        self.batch_selector_combo.blockSignals(True)
        self.batch_selector_combo.clear()
        
        batches = self.undo_manager.get_undoable_batches()
        for batch in batches:
            self.batch_selector_combo.addItem(batch.description, batch.batch_id)
        
        self.batch_selector_combo.blockSignals(False)
        self._on_batch_selected()

    def _on_batch_selected(self) -> None:
        """Handle batch selection for update/delete modes."""
        if self.batch_selector_combo.currentIndex() >= 0:
            self.selected_batch_for_operation = self.batch_selector_combo.currentData()
            self._update_validation()
        else:
            self.selected_batch_for_operation = None
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
        
        self.update_thread = QtCore.QThread()
        self.update_worker = UpdateWorker(
            self.api,
            calendar_id,
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
        
        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete {len(batch.events)} events from batch:\n{batch.description}?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
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
        # NEW: Use add_operation() instead of add_batch()
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
        """Undo the selected batch of events."""
        # Get the selected batch from the combo box
        selected_index = self.undo_combo.currentIndex()
        if selected_index < 0:
            return

        batch_id = self.undo_combo.currentData()
        if not batch_id:
            return

        batch = self.undo_manager.get_batch_by_id(batch_id)
        if not batch or self._undo_running():
            return

        # Get events to undo from the selected batch
        events_to_undo = batch.events

        self.undo_thread = QtCore.QThread()
        self.undo_worker = UndoWorker(
            self.api,
            events_to_undo,
            send_email=self.send_email_checkbox.isChecked(),
            notification_email=self.notification_email.text(),
            batch_description=batch.description,
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
        self.undo_thread.start()

    def _on_undo_finished(self, deleted_event_ids: list[str]) -> None:
        self._append_log(f"Undo complete. Deleted {len(deleted_event_ids)} events.")

        # Mark the selected batch as undone in undo manager
        selected_index = self.undo_combo.currentIndex()
        if selected_index >= 0:
            batch_id = self.undo_combo.currentData()
            if batch_id:
                self.undo_manager.undo_batch(batch_id)

        # Auto-save immediately after undo to persist the updated state
        self.undo_manager.save_history(str(self._app_data_dir))

        self.created_events = []
        self._stop_thread(self.undo_thread, self.undo_worker)
        self.undo_thread = None
        self.undo_worker = None
        self._toggle_inputs(True)
        self._update_validation()
        self._update_undo_ui()

    def _on_undo_error(self, message: str) -> None:
        self._append_log(f"Undo error: {message}")
        QtWidgets.QMessageBox.critical(self, "Undo error", message)
        self._stop_thread(self.undo_thread, self.undo_worker)
        self.undo_thread = None
        self.undo_worker = None
        self._toggle_inputs(True)
        self._update_validation()

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
        
        # NEW: Record delete operation for redo capability
        if self.delete_worker and hasattr(self.delete_worker, 'deleted_snapshots'):
            deleted_snapshots = self.delete_worker.deleted_snapshots
            self.undo_manager.add_operation(
                operation_type="delete",
                affected_event_ids=deleted_event_ids,
                event_snapshots=deleted_snapshots,
                description=f"Deleted: {batch_description}",
            )
            self.undo_manager.save_history(str(self._app_data_dir))
        
        # Also mark original batch as undone (for backwards compat)
        if self.selected_batch_for_operation:
            try:
                self.undo_manager.undo_batch(self.selected_batch_for_operation)
            except ValueError:
                pass  # Batch already undone or not found
        
        self._stop_thread(self.delete_thread, self.delete_worker)
        self.delete_thread = None
        self.delete_worker = None
        self._toggle_inputs(True)
        self._update_validation()
        self._update_undo_ui()
        self._switch_mode("create")  # Switch back to create mode

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
        
        # NEW: Record as single "update" operation with both old and new snapshots
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
        self._switch_mode("create")  # Switch back to create mode

    def _append_log(self, message: str) -> None:
        self.log_box.appendPlainText(message)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )

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
            self.start_time,
            self.day_length,
            self.calendar_combo,
            self.send_email_checkbox,
            *self.weekday_boxes.values(),
        ):
            widget.setEnabled(enabled)

    def _creation_running(self) -> bool:
        return bool(self.creation_thread and self.creation_thread.isRunning())

    def _undo_running(self) -> bool:
        return bool(self.undo_thread and self.undo_thread.isRunning())

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

    def _update_undo_combo_box(self) -> None:
        """Update the undo combo box with available undoable batches."""
        current_data = self.undo_combo.currentData()

        self.undo_combo.clear()

        # Get all undoable batches
        batches = self.undo_manager.get_undoable_batches()

        for batch in batches:
            self.undo_combo.addItem(batch.description, batch.batch_id)

        # Restore previous selection if possible
        if current_data and current_data in [
            self.undo_combo.itemData(i) for i in range(self.undo_combo.count())
        ]:
            index = self.undo_combo.findData(current_data)
            if index >= 0:
                self.undo_combo.setCurrentIndex(index)
        elif batches:
            # Select the most recent batch by default
            self.undo_combo.setCurrentIndex(0)

    def _update_undo_button_state(self) -> None:
        """Update the undo button state based on combo box selection."""
        self.undo_button.setEnabled(
            self.undo_combo.currentIndex() >= 0
            and not self._creation_running()
            and not self._undo_running()
        )

    def _update_undo_ui(self) -> None:
        """Update undo-related UI elements based on current undo state."""
        # Update undo combo box with available batches
        self._update_undo_combo_box()

        # Update undo button state
        self._update_undo_button_state()

        # Update status bar undo info
        stats = self.undo_manager.get_history_stats()
        undoable_batches = stats["undoable_batches"]
        undoable_events = stats["undoable_events"]
        self.undo_status_label.setText(
            f"{undoable_batches} batches ({undoable_events} events) to undo"
        )

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

        self._stop_thread(self.creation_thread, self.creation_worker)
        self._stop_thread(self.undo_thread, self.undo_worker)

        super().closeEvent(event)


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
