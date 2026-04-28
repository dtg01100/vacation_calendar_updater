# AGENTS.md

**Version:** 1.0
**Date:** 2026-04-28
**Purpose:** Technical reference for Vacation Calendar Updater development

---

## Project Overview

**Vacation Calendar Updater** is a PySide6-based GUI application for managing vacation calendar events in Google Calendar.

- **Language:** Python 3.10+
- **Framework:** PySide6 (Qt for Python)
- **APIs:** Google Calendar API, Gmail API
- **Distribution:** Flatpak packaging

---

## Quick Setup

```bash
# Install dependencies
pip install -e .

# Run the application
python -m app.main
# or
vacation-calendar

# Development mode (with GUI)
python -m app.main

# Run tests
pytest

# Lint with ruff
ruff check .

# Format with ruff
ruff format .
```

---

## Architecture

```
User Input (MainWindow)
    |
    v
Mode Selection (create | update | delete | import)
    |
    v
Workers (Qt QThread workers for async operations)
    |
    +-- EventCreationWorker  - Create calendar events
    +-- DeleteWorker         - Delete events
    +-- UpdateWorker         - Update events
    +-- UndoWorker           - Undo operations
    +-- RedoWorker           - Redo operations
    +-- StartupWorker        - Initial calendar loading
    +-- ImportFetchWorker    - Import batch fetching
    |
    v
GoogleApi (services.py)
    |
    v
Google Calendar / Gmail APIs
```

**Key Modules:**

| Module | Purpose |
|--------|---------|
| `app/main.py` | Application entry point |
| `app/ui/main_window.py` | Main window with all modes |
| `app/services.py` | Google Calendar API wrapper |
| `app/workers.py` | Background workers for async operations |
| `app/undo_manager.py` | Undo/redo state management |
| `app/validation.py` | Input validation and date parsing |
| `app/config.py` | Configuration management |

---

## Directory Structure

| Path | Purpose |
|------|---------|
| `app/` | Main application code |
| `app/ui/` | UI widgets and dialogs |
| `tests/` | pytest-based unit and integration tests |
| `flatpak/` | Flatpak build configuration and assets |
| `flatpak-builder-tools/` | Submodule for pip generator |
| `.devcontainer/` | Development container config |

---

## Code Style

**Python Conventions:**

- Python 3.10+ with `from __future__ import annotations`
- **Type hints** required for all function signatures
- **4 spaces** indentation (never tabs)
- **UTF-8 encoding** for all files
- **Dataclasses** for data structures
- **Qt signals/slots** for async communication

**Module Structure:**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only for type hints, not runtime imports
    from .services import EnhancedCreatedEvent

import datetime as dt

from PySide6.QtCore import QObject, Signal

class MyClass:
    """Brief description of class purpose."""
    
    my_signal = Signal(str)
    
    def __init__(self) -> None:
        """Initialize the class."""
        pass
    
    def my_method(self, arg: str) -> None:
        """Describe what the method does.

        Args:
            arg: Description of argument

        Returns:
            Description of return value
        """
        pass
```

**Imports:**

```python
# Standard library first
import datetime as dt
import uuid
from abc import abstractmethod
from collections.abc import Iterable

# Third-party
from PySide6.QtCore import QObject, Signal, Slot

# Local application
from .services import CreatedEvent, GoogleApi
from .validation import ScheduleRequest
```

---

## Testing

**Before Committing:**

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/test_workers.py

# Lint check
ruff check .

# Format check
ruff format --check .
```

**Test Structure:**

| File | Purpose |
|------|---------|
| `tests/conftest.py` | Shared fixtures (QtBot, QApplication) |
| `tests/test_*.py` | Unit tests for specific modules |
| `tests/test_*_ui.py` | UI integration tests |

**Testing Patterns:**

```python
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

# Use qtbot fixture for widget lifecycle
def test_something(qtbot):
    widget = MyWidget()
    qtbot.addWidget(widget)
    # Test widget behavior
    widget.close()
```

---

## Commit Format

```
type(scope): brief description

Problem: What was broken/incomplete
Solution: How you fixed it
Testing: How you verified the fix
```

**Types:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

**Example:**

```bash
git add -A
git commit -m "fix(workers): handle HttpError 404 in delete operations

Problem: Delete worker would crash when event already deleted on server
Solution: Added 404/410 handling to skip rather than crash
Testing: Added test_delete_already_deleted test, all tests pass"
```

**Pre-Commit Checklist:**

- `pytest` passes on all changed files
- `ruff check .` reports no errors
- Type hints complete
- Commit message explains WHAT and WHY

---

## Common Patterns

**Qt Worker Pattern:**

```python
from PySide6.QtCore import QObject, Signal, Slot

class MyWorker(QObject):
    progress = Signal(str)
    error = Signal(str)
    finished = Signal()

    def __init__(self, api: GoogleApi) -> None:
        super().__init__()
        self.api = api

    @Slot()
    def run(self) -> None:
        try:
            # Do work
            self.progress.emit("Working...")
            # More work
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))
```

**Connecting Workers:**

```python
self.worker = MyWorker(api)
self.thread = QThread(self)
self.worker.moveToThread(self.thread)
self.thread.started.connect(self.worker.run)
self.worker.finished.connect(self._on_finished)
self.thread.start()
```

**Date/Time Parsing:**

```python
from dateutil.parser import parse

# Parse various formats
date = parse("2026-04-28").date()
time = parse("09:00").time()

# Normalize Qt types
from PySide6.QtCore import QDate, QTime
qdate = QDate.currentDate()
python_date = qdate.toPython()
```

---

## Documentation

### What Needs Documentation

| Change Type | Required Documentation |
|-------------|------------------------|
| New feature | Update relevant section in AGENTS.md |
| API change | Update docstrings in services.py |
| UI component | Add class docstring in ui module |
| Worker change | Update worker docstring |

---

## Anti-Patterns (What NOT To Do)

| Anti-Pattern | Why It's Wrong | What To Do |
|--------------|----------------|------------|
| Blocking UI in worker | Qt requires workers on separate threads | Use QThread with worker.moveToThread() |
| Bare `except Exception` | Catches too much, hides bugs | Catch specific exceptions |
| Missing type hints | Hard to understand function contracts | Add `-> None`, `-> str`, etc. |
| Direct API calls in UI | Couples UI to network | Use workers for all API calls |
| Forgetting `from __future__ import annotations` | Breaks type hints with circular imports | Always include at top of Python files |

---

## Quick Reference

```bash
# Run application
python -m app.main

# Run tests
pytest

# Lint
ruff check .

# Format
ruff format .

# Build Flatpak
./build-flatpak.sh bundle

# Install Flatpak locally
./build-flatpak.sh install
```

---

*For project methodology and workflow, see .clio/instructions.md*