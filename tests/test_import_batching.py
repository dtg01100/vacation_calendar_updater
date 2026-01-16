"""Unit tests for import logic without full UI initialization."""
from __future__ import annotations

import datetime as dt

from app.services import EnhancedCreatedEvent


def create_sample_event(
    event_id: str, summary: str, start_date: str, end_date: str
) -> dict:
    return {
        "id": event_id,
        "summary": summary,
        "start": {"date": start_date},
        "end": {"date": end_date},
    }


def group_events_into_batches(items: list, calendar_id: str) -> list[dict]:
    """Replicate the batching logic from MainWindow."""
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
            start_time = dt.datetime.fromisoformat(
                start["dateTime"].replace("Z", "+00:00")
            )
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
            request_snapshot=None,
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
                        batches.append(
                            {
                                "description": f"{summary} ({current_batch[0].start_time.date()} - {current_batch[-1].start_time.date()})",
                                "events": current_batch,
                                "event_count": len(current_batch),
                            }
                        )
                    current_batch = [event]

        # Add final batch
        if len(current_batch) > 0:
            batches.append(
                {
                    "description": f"{summary} ({current_batch[0].start_time.date()} - {current_batch[-1].start_time.date()})",
                    "events": current_batch,
                    "event_count": len(current_batch),
                }
            )

    return batches


class TestImportBatchingLogic:
    """Test event batching logic in isolation."""

    def test_group_single_event(self):
        """Group a single event."""
        items = [create_sample_event("e1", "Vacation", "2024-01-15", "2024-01-16")]
        batches = group_events_into_batches(items, "cal_001")

        assert len(batches) == 1
        assert batches[0]["event_count"] == 1
        assert batches[0]["description"].startswith("Vacation")

    def test_group_adjacent_events_same_batch(self):
        """Group adjacent events into same batch."""
        items = [
            create_sample_event("e1", "Trip", "2024-01-01", "2024-01-02"),
            create_sample_event("e2", "Trip", "2024-01-02", "2024-01-03"),
            create_sample_event("e3", "Trip", "2024-01-03", "2024-01-04"),
        ]
        batches = group_events_into_batches(items, "cal_001")

        # Should create 1 batch (all adjacent, <= 3 days apart)
        assert len(batches) == 1
        assert batches[0]["event_count"] == 3

    def test_group_events_with_gap_separate_batches(self):
        """Group events with gap > 3 days into separate batches."""
        items = [
            create_sample_event("e1", "Trip", "2024-01-01", "2024-01-02"),
            create_sample_event("e2", "Trip", "2024-01-10", "2024-01-11"),  # 9 days later
        ]
        batches = group_events_into_batches(items, "cal_001")

        # Should create 2 batches
        assert len(batches) == 2
        assert batches[0]["event_count"] == 1
        assert batches[1]["event_count"] == 1

    def test_group_multiple_summaries_separate_batches(self):
        """Group events with different summaries into separate batches."""
        items = [
            create_sample_event("e1", "Vacation", "2024-01-01", "2024-01-02"),
            create_sample_event("e2", "Conference", "2024-01-03", "2024-01-04"),
        ]
        batches = group_events_into_batches(items, "cal_001")

        # Should create 2 batches (different summaries)
        assert len(batches) == 2

    def test_group_handles_missing_end(self):
        """Handle events with missing end time gracefully."""
        items = [
            create_sample_event("e1", "Event", "2024-01-01", "2024-01-02"),
            {
                "id": "e2",
                "summary": "Event",
                "start": {"date": "2024-01-02"},
                # Missing end
            },
        ]
        batches = group_events_into_batches(items, "cal_001")

        # Should handle gracefully - only e1 should be included
        assert len(batches) >= 1

    def test_batch_has_required_fields(self):
        """Verify batch has required fields for UI display."""
        items = [create_sample_event("e1", "Vacation", "2024-01-15", "2024-01-16")]
        batches = group_events_into_batches(items, "cal_001")

        assert len(batches) == 1
        batch = batches[0]
        assert "description" in batch
        assert "events" in batch
        assert "event_count" in batch
        assert isinstance(batch["events"], list)
        assert isinstance(batch["event_count"], int)

    def test_batch_events_are_enhanced_created_events(self):
        """Verify batches contain EnhancedCreatedEvent objects."""
        items = [create_sample_event("e1", "Vacation", "2024-01-15", "2024-01-16")]
        batches = group_events_into_batches(items, "cal_001")

        assert len(batches) == 1
        assert len(batches[0]["events"]) == 1
        event = batches[0]["events"][0]
        assert isinstance(event, EnhancedCreatedEvent)
        assert event.event_id == "e1"
        assert event.event_name == "Vacation"
        assert event.calendar_id == "cal_001"

    def test_empty_items_returns_empty_batches(self):
        """Empty items should return empty batches."""
        batches = group_events_into_batches([], "cal_001")
        assert len(batches) == 0

    def test_gap_exactly_3_days_same_batch(self):
        """Events 3 days apart should be in same batch."""
        items = [
            create_sample_event("e1", "Trip", "2024-01-01", "2024-01-02"),
            create_sample_event("e2", "Trip", "2024-01-04", "2024-01-05"),  # 3 days later
        ]
        batches = group_events_into_batches(items, "cal_001")

        # Gap is exactly 3 days, should be same batch
        assert len(batches) == 1
        assert batches[0]["event_count"] == 2

    def test_gap_4_days_separate_batches(self):
        """Events 4 days apart should be in separate batches."""
        items = [
            create_sample_event("e1", "Trip", "2024-01-01", "2024-01-02"),
            create_sample_event("e2", "Trip", "2024-01-05", "2024-01-06"),  # 4 days later
        ]
        batches = group_events_into_batches(items, "cal_001")

        # Gap is 4 days, should be separate batches
        assert len(batches) == 2
