from __future__ import annotations

import datetime as dt
import uuid
from typing import Iterable

from googleapiclient.errors import HttpError
from PySide6.QtCore import QObject, QThread, Signal, Slot

from .services import CreatedEvent, EnhancedCreatedEvent, GoogleApi
from .validation import ScheduleRequest, build_schedule


class EventCreationWorker(QObject):
    finished = Signal(list)  # List[EnhancedCreatedEvent]
    progress = Signal(str)
    error = Signal(str)
    stopped = Signal()

    def __init__(self, api: GoogleApi, calendar_id: str, request: ScheduleRequest) -> None:
        super().__init__()
        self.api = api
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
                self.api.send_email(
                    self.request.notification_email,
                    f"{self.request.event_name} Calendar Event Created ({self.request.start_date}_{self.request.end_date})",
                    message_text,
                    enabled=self.request.send_email,
                )
                if self.request.send_email:
                    self.progress.emit("Notification email sent")
            self.finished.emit(created)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class UndoWorker(QObject):
    finished = Signal(list)  # List of deleted event IDs
    progress = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        api: GoogleApi,
        events: Iterable[EnhancedCreatedEvent],
        *,
        send_email: bool,
        notification_email: str,
        batch_description: str = "",
    ) -> None:
        super().__init__()
        self.api = api
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
                basic_event = CreatedEvent(event_id=event.event_id, calendar_id=event.calendar_id)
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
                message_text += f"Deleted on: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                self.api.send_email(
                    self.notification_email,
                    f"Calendar Events Deleted - {counter} events",
                    message_text,
                    enabled=self.send_email,
                )
                if self.send_email:
                    self.progress.emit("Deletion email sent")
            self.finished.emit(deleted_event_ids)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class StartupWorker(QThread):
    """Worker thread to load user email and calendar list in background."""

    finished = Signal(tuple)  # (user_email, (calendar_names, calendar_items))
    error = Signal(str)

    def __init__(self, api: "GoogleApi") -> None:
        super().__init__()
        self.api = api

    def run(self) -> None:
        try:
            user_email = self.api.user_email()
            calendar_names, calendar_items = self.api.list_calendars()
            self.finished.emit((user_email, (calendar_names, calendar_items)))
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
