"""Tests for ImportFetchWorker to ensure dt is available and grouping runs."""
from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pytest

from app.ui.main_window import MainWindow


class _FakeEventsList:
    def __init__(self, items):
        self._items = items

    def execute(self):
        return {"items": self._items}


class _FakeEvents:
    def __init__(self, items):
        self._items = items

    def list(self, **kwargs):
        # ensure timeMin/timeMax provided
        assert "timeMin" in kwargs and "timeMax" in kwargs
        return _FakeEventsList(self._items)


class _FakeService:
    def __init__(self, items):
        self._events = _FakeEvents(items)

    def events(self):
        return self._events


@pytest.fixture
def sample_items():
    return [
        {
            "id": "e1",
            "summary": "Trip",
            "start": {"date": "2024-01-01"},
            "end": {"date": "2024-01-02"},
        },
        {
            "id": "e2",
            "summary": "Trip",
            "start": {"date": "2024-01-03"},
            "end": {"date": "2024-01-04"},
        },
    ]


def test_import_worker_run_uses_dt_and_emits_batches(sample_items):
    # Arrange
    api = MagicMock()
    api.calendar_service.return_value = _FakeService(sample_items)

    emitted_batches = []

    def group_func(items, calendar_id):
        emitted_batches.append({"items": items, "calendar": calendar_id})
        return [items]

    worker = MainWindow.ImportFetchWorker(
        api=api,
        calendar_id="cal_123",
        start_dt=dt.date(2024, 1, 1),
        end_dt=dt.date(2024, 1, 31),
        group_func=group_func,
    )

    # Act: calling run should not raise NameError for dt and should emit finished
    worker.run()

    # Assert
    assert emitted_batches, "group_func should have been called with items"
