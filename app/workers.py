from __future__ import annotations

import datetime as dt
import uuid
from abc import abstractmethod
from collections.abc import Iterable

from googleapiclient.errors import HttpError
from PySide6.QtCore import QObject, QThread, Signal, Slot

from .services import CreatedEvent, EnhancedCreatedEvent, GoogleApi
from .validation import ScheduleRequest, build_schedule


class BaseWorker(QObject):
    """Abstract base worker with common functionality for all workers."""

    progress = Signal(str)
    error = Signal(str)

    def __init__(self, api: GoogleApi) -> None:
        super().__init__()
        self.api = api

    @abstractmethod
    @Slot()
    def run(self) -> None:
        """Implement in subclass to perform the worker's task."""
        pass

    def send_notification_email(
        self, recipient: str, subject: str, body: str, *, enabled: bool
    ) -> None:
        """Send notification email if enabled, with progress update.

        Args:
            recipient: Email address to send to
            subject: Email subject line
            body: Email body text
            enabled: Whether email sending is enabled
        """
        try:
            self.api.send_email(recipient, subject, body, enabled=enabled)
            if enabled:
                self.progress.emit("Notification email sent")
        except Exception as e:
            self.progress.emit(f"Email notification failed: {e}")

    def safe_run(self) -> None:
        """Wrapper with standard error handling."""
        try:
            self.run()
        except Exception as exc:
            self.error.emit(str(exc))


class EventCreationWorker(BaseWorker):
    finished = Signal(list)  # List[EnhancedCreatedEvent]
    stopped = Signal()

    def __init__(
        self, api: GoogleApi, calendar_id: str, request: ScheduleRequest
    ) -> None:
        super().__init__(api)
        self.calendar_id = calendar_id
        self.request = request
        self._stop_requested = False
        self.batch_id = uuid.uuid4().hex

    def stop(self) -> None:
        self._stop_requested = True

    @Slot()
    def run(self) -> None:
        try:
            created: list[EnhancedCreatedEvent] = []
            schedule = build_schedule(self.request)
            total_hours = 0.0
            created_at = dt.datetime.now()

            # Create a snapshot of the request for undo purposes
            request_snapshot = {
                "event_name": self.request.event_name,
                "notification_email": self.request.notification_email,
                "calendar_name": self.request.calendar_name,
                "start_date": self.request.start_date.isoformat(),
                "end_date": self.request.end_date.isoformat(),
                "start_time": self.request.start_time.isoformat(),
                "day_length_hours": self.request.day_length_hours,
                "weekdays": dict(self.request.weekdays),
                "send_email": self.request.send_email,
            }

            for start, end in schedule:
                if self._stop_requested:
                    self.progress.emit("Stopped before completion")
                    self.stopped.emit()
                    return

                # Create the basic event using the existing API
                basic_event = self.api.create_event(
                    self.calendar_id, self.request.event_name, start, end
                )

                # Create enhanced event with additional metadata
                enhanced_event = EnhancedCreatedEvent(
                    event_id=basic_event.event_id,
                    calendar_id=basic_event.calendar_id,
                    event_name=self.request.event_name,
                    start_time=start,
                    end_time=end,
                    created_at=created_at,
                    batch_id=self.batch_id,
                    request_snapshot=request_snapshot,
                )
                created.append(enhanced_event)
                total_hours += self.request.day_length_hours
                self.progress.emit(
                    f"Created event on {start.date()} from {start.time()} to {end.time()}"
                )

            if created:
                message_text = (
                    f'Calendar event(s) created for "{self.request.event_name}" event, for {total_hours} hours, '
                    f"over the course of {len(created)} days. The event days are between {self.request.start_date} and {self.request.end_date}."
                )
                self.send_notification_email(
                    self.request.notification_email,
                    f"{self.request.event_name} Calendar Event Created ({self.request.start_date}_{self.request.end_date})",
                    message_text,
                    enabled=self.request.send_email,
                )
            self.finished.emit(created)
        except Exception as exc:
            self.error.emit(str(exc))


class UndoWorker(BaseWorker):
    finished = Signal(list)  # List of deleted event IDs

    def __init__(
        self,
        api: GoogleApi,
        events: Iterable[EnhancedCreatedEvent],
        *,
        send_email: bool,
        notification_email: str,
        batch_description: str = "",
    ) -> None:
        super().__init__(api)
        self.events = list(events)
        self.send_email = send_email
        self.notification_email = notification_email
        self.batch_description = batch_description

    @Slot()
    def run(self) -> None:
        try:
            deleted_event_ids = []
            skipped_events = []
            counter = 0
            event_names = set()

            for event in self.events:
                # Create a basic CreatedEvent for the API
                basic_event = CreatedEvent(
                    event_id=event.event_id, calendar_id=event.calendar_id
                )
                try:
                    self.api.delete_event(basic_event)
                    deleted_event_ids.append(event.event_id)
                    event_names.add(event.event_name)
                    counter += 1
                    self.progress.emit(
                        f"Deleted event {event.event_id} ({event.event_name}) on {event.start_time.date()}"
                    )
                except HttpError as e:
                    # Handle events that no longer exist (404 or 410 status)
                    if e.resp.status in (404, 410):
                        skipped_events.append(event)
                        self.progress.emit(
                            f"Skipped event {event.event_id} ({event.event_name}) - already deleted or not found"
                        )
                        # Still count as processed since it's gone from calendar
                        deleted_event_ids.append(event.event_id)
                    else:
                        # Re-raise other HTTP errors
                        raise

            if counter or skipped_events:
                # Create detailed email message
                event_names_str = ", ".join(sorted(event_names))
                message_text = f"{counter} calendar event(s) deleted:\n\n"
                message_text += f"Event name(s): {event_names_str}\n"
                message_text += f"Batch: {self.batch_description}\n"
                if skipped_events:
                    message_text += f"\n{len(skipped_events)} event(s) were already deleted or not found\n"
                message_text += (
                    f"Deleted on: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

                self.send_notification_email(
                    self.notification_email,
                    f"Calendar Events Deleted - {counter} events",
                    message_text,
                    enabled=self.send_email,
                )
            self.finished.emit(deleted_event_ids)
        except Exception as exc:
            self.error.emit(str(exc))


class RedoWorker(BaseWorker):
    """Worker to recreate a batch of previously deleted events."""

    finished = Signal(list)  # List of recreated event IDs

    def __init__(
        self,
        api: GoogleApi,
        events: Iterable[EnhancedCreatedEvent],
        batch_description: str = "",
    ) -> None:
        super().__init__(api)
        self.events = list(events)
        self.batch_description = batch_description
        self._stop_requested = False

    def stop(self) -> None:
        """Request the redo operation to stop gracefully."""
        self._stop_requested = True

    @Slot()
    def run(self) -> None:
        try:
            recreated_event_ids = []
            skipped_events = []
            counter = 0
            event_names = set()

            for event in self.events:
                if self._stop_requested:
                    self.progress.emit("Redo cancelled by user")
                    break

                try:
                    # Recreate the event using the stored snapshots
                    created_event = self.api.create_event(
                        event.calendar_id,
                        event.event_name,
                        event.start_time,
                        event.end_time,
                    )
                    recreated_event_ids.append(created_event.event_id)
                    event_names.add(event.event_name)
                    counter += 1
                    self.progress.emit(
                        f"Recreated event {created_event.event_id} ({event.event_name}) on {event.start_time.date()}"
                    )
                except HttpError as e:
                    # Handle events that cannot be recreated
                    if e.resp.status in (404, 410):
                        skipped_events.append(event)
                        self.progress.emit(
                            f"Skipped event {event.event_id} ({event.event_name}) - calendar not found"
                        )
                    else:
                        # Re-raise other HTTP errors
                        raise

            if counter or skipped_events:
                # Create detailed progress message
                event_names_str = ", ".join(sorted(event_names))
                self.progress.emit(
                    f"Redo complete: {counter} calendar event(s) recreated"
                )
                if skipped_events:
                    self.progress.emit(
                        f"{len(skipped_events)} event(s) could not be recreated"
                    )

            self.finished.emit(recreated_event_ids)
        except Exception as exc:
            self.error.emit(str(exc))


class StartupWorker(QThread):
    """Worker thread to load user email and calendar list in background."""

    finished = Signal(tuple)  # (user_email, (calendar_names, calendar_items))
    error = Signal(str)

    def __init__(self, api: GoogleApi) -> None:
        super().__init__()
        self.api = api

    def run(self) -> None:
        try:
            user_email = self.api.user_email()
            calendar_names, calendar_items = self.api.list_calendars()
            self.finished.emit((user_email, (calendar_names, calendar_items)))
        except Exception as exc:
            self.error.emit(str(exc))

class DeleteWorker(BaseWorker):
    """Worker to delete a batch of events from the calendar."""

    finished = Signal(list, str)  # (deleted_event_ids, batch_description)

    def __init__(
        self,
        api: GoogleApi,
        events: Iterable[EnhancedCreatedEvent],
        *,
        send_email: bool,
        notification_email: str,
        batch_description: str = "",
    ) -> None:
        super().__init__(api)
        self.events = list(events)
        self.send_email = send_email
        self.notification_email = notification_email
        self.batch_description = batch_description
        self.deleted_snapshots = []  # For redo capability

    @Slot()
    def run(self) -> None:
        try:
            deleted_event_ids = []
            skipped_events = []
            counter = 0
            event_names = set()
            self.deleted_snapshots = []  # Reset snapshots

            for event in self.events:
                basic_event = CreatedEvent(
                    event_id=event.event_id, calendar_id=event.calendar_id
                )
                try:
                    self.api.delete_event(basic_event)
                    deleted_event_ids.append(event.event_id)
                    self.deleted_snapshots.append(event)  # NEW: preserve snapshot
                    event_names.add(event.event_name)
                    counter += 1
                    self.progress.emit(
                        f"Deleted event {event.event_id} ({event.event_name}) on {event.start_time.date()}"
                    )
                except HttpError as e:
                    if e.resp.status in (404, 410):
                        skipped_events.append(event)
                        self.progress.emit(
                            f"Skipped event {event.event_id} ({event.event_name}) - already deleted or not found"
                        )
                        deleted_event_ids.append(event.event_id)
                        self.deleted_snapshots.append(event)  # NEW: preserve even if not found
                    else:
                        raise

            if counter or skipped_events:
                event_names_str = ", ".join(sorted(event_names))
                message_text = f"{counter} calendar event(s) deleted:\n\n"
                message_text += f"Event name(s): {event_names_str}\n"
                message_text += f"Batch: {self.batch_description}\n"
                if skipped_events:
                    message_text += f"\n{len(skipped_events)} event(s) were already deleted or not found\n"
                message_text += (
                    f"Deleted on: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

                self.send_notification_email(
                    self.notification_email,
                    f"Calendar Events Deleted - {counter} events",
                    message_text,
                    enabled=self.send_email,
                )
            self.finished.emit(deleted_event_ids, self.batch_description)
        except Exception as exc:
            self.error.emit(str(exc))


class UpdateWorker(BaseWorker):
    """Worker to update a batch of events with a new schedule."""

    finished = Signal(list, list)  # (new_events, old_event_snapshots)

    def __init__(
        self,
        api: GoogleApi,
        calendar_id: str,
        old_events: Iterable[EnhancedCreatedEvent],
        new_request: ScheduleRequest,
        *,
        send_email: bool,
        notification_email: str,
    ) -> None:
        super().__init__(api)
        self.calendar_id = calendar_id
        self.old_events = list(old_events)
        self.new_request = new_request
        self.send_email = send_email
        self.notification_email = notification_email
        self.batch_id = uuid.uuid4().hex

    @Slot()
    def run(self) -> None:
        try:
            # Preserve old events for operation snapshot (before deletion)
            old_event_snapshots = list(self.old_events)

            # Step 1: Delete old events
            deleted_count = 0
            for event in self.old_events:
                basic_event = CreatedEvent(
                    event_id=event.event_id, calendar_id=event.calendar_id
                )
                try:
                    self.api.delete_event(basic_event)
                    deleted_count += 1
                    self.progress.emit(
                        f"Deleted old event {event.event_id} on {event.start_time.date()}"
                    )
                except HttpError as e:
                    if e.resp.status not in (404, 410):
                        raise
                    self.progress.emit(f"Skipped old event {event.event_id} - already gone")
                    deleted_count += 1

            self.progress.emit(f"Deleted {deleted_count} old events")

            # Step 2: Create new events with updated schedule
            created: list[EnhancedCreatedEvent] = []
            schedule = build_schedule(self.new_request)
            total_hours = 0.0
            created_at = dt.datetime.now()

            request_snapshot = {
                "event_name": self.new_request.event_name,
                "notification_email": self.new_request.notification_email,
                "calendar_name": self.new_request.calendar_name,
                "start_date": self.new_request.start_date.isoformat(),
                "end_date": self.new_request.end_date.isoformat(),
                "start_time": self.new_request.start_time.isoformat(),
                "day_length_hours": self.new_request.day_length_hours,
                "weekdays": dict(self.new_request.weekdays),
                "send_email": self.new_request.send_email,
            }

            for start, end in schedule:
                basic_event = self.api.create_event(
                    self.calendar_id, self.new_request.event_name, start, end
                )

                enhanced_event = EnhancedCreatedEvent(
                    event_id=basic_event.event_id,
                    calendar_id=basic_event.calendar_id,
                    event_name=self.new_request.event_name,
                    start_time=start,
                    end_time=end,
                    created_at=created_at,
                    batch_id=self.batch_id,
                    request_snapshot=request_snapshot,
                )
                created.append(enhanced_event)
                total_hours += self.new_request.day_length_hours
                self.progress.emit(
                    f"Created updated event on {start.date()} from {start.time()} to {end.time()}"
                )

            # Step 3: Send notification
            if created:
                message_text = (
                    f'Calendar event(s) updated for "{self.new_request.event_name}", for {total_hours} hours, '
                    f"over {len(created)} days. New dates: {self.new_request.start_date} to {self.new_request.end_date}."
                )
                self.send_notification_email(
                    self.new_request.notification_email,
                    f"{self.new_request.event_name} Calendar Event Updated ({self.new_request.start_date}_{self.new_request.end_date})",
                    message_text,
                    enabled=self.new_request.send_email,
                )

            # NEW: Emit both old and new events for atomic operation recording
            self.finished.emit(created, old_event_snapshots)
        except Exception as exc:
            self.error.emit(str(exc))