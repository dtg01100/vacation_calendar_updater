# Design: Comprehensive Testing Initiative

## Context

### Background

The Vacation Calendar Updater is a PySide6-based Qt application that manages Google Calendar events. It has 30+ existing test files but lacks:

1. **Integration tests** - End-to-end workflow tests covering entire user journeys
2. **API mocking** - Tests currently require network access to Google APIs
3. **Coverage enforcement** - No automated coverage thresholds in CI

### Current State

- **Unit tests exist:** `tests/test_*.py` files covering individual modules
- **conftest.py exists:** Basic `qapp` and `qtbot` fixtures
- **No integration tests:** No tests covering complete workflows
- **No API mocking:** Tests call actual Google APIs (requires credentials)
- **No coverage gates:** Coverage is not enforced in CI

### Constraints

1. **pytest-qt unavailable** - Using custom QtBot implementation
2. **PySide6 required** - UI tests must use QApplication
3. **Google API dependencies** - Services module has complex initialization

---

## Goals / Non-Goals

### Goals

1. Add integration tests for all four modes (Create, Update, Delete, Import)
2. Implement API mocking to enable offline testing
3. Add coverage enforcement with configurable thresholds
4. Create reusable fixtures for common test scenarios
5. Integrate coverage reporting into CI/CD pipeline

### Non-Goals

1. **Not** rewriting existing unit tests
2. **Not** adding tests for third-party libraries (Google APIs)
3. **Not** implementing GUI screenshot testing
4. **Not** adding performance benchmarking (separate initiative)

---

## Decisions

### Decision 1: Use `responses` library for API mocking

**Choice:** Use the `responses` library to mock HTTP requests to Google APIs.

**Rationale:**
- `responses` is lightweight and well-maintained
- It intercepts requests at the HTTP level, matching how the actual client works
- Compatible with `httplib2` which the Google API client uses
- Easier to maintain than subclassing GoogleApi

**Alternative considered:** Subclass GoogleApi with mock - rejected because it would require changes to production code and wouldn't test actual serialization.

---

### Decision 2: Fixtures in `conftest.py` + `tests/fixtures/` directory

**Choice:** Keep simple fixtures in `conftest.py` and create a `tests/fixtures/` directory for complex fixtures.

**Rationale:**
- `conftest.py` already exists and contains session-scoped fixtures
- Complex fixtures (mock_api, sample_batch) benefit from being in separate files for maintainability
- Follows pytest conventions for fixture organization

---

### Decision 3: Coverage threshold of 80% overall, 90% for workers

**Choice:** Set 80% overall coverage as minimum, with 90% requirement for `app/workers.py`.

**Rationale:**
- 80% is achievable without excessive test bureaucracy
- Workers module is critical path (all event operations go through it) and warrants higher coverage
- Validation module at 85% due to complex date parsing logic

---

### Decision 4: Integration tests in `tests/integration/` subdirectory

**Choice:** Create `tests/integration/` directory for end-to-end workflow tests.

**Rationale:**
- Clear separation between unit tests (`tests/test_*.py`) and integration tests (`tests/integration/*.py`)
- Allows running unit tests without integration tests (faster feedback)
- Allows running integration tests only when needed

---

## Risks / Trade-offs

### Risk 1: API mocking may drift from actual behavior

**Mitigation:** Review mock responses against actual Google API responses when changes occur. Add integration test marker for tests that require real API.

### Risk 2: Fixtures may become a maintenance burden

**Mitigation:** Keep fixtures focused on common scenarios. If a fixture becomes too complex, extract to a helper module.

### Risk 3: Coverage enforcement may block contributions

**Mitigation:** Allow exemptions with justification. Coverage requirements apply to new code, not legacy code.

---

## Implementation Approach

### Phase 1: Fixtures
1. Enhance `tests/conftest.py` with mock_api fixture
2. Create `tests/fixtures/mock_api.py` for Google API mocking
3. Add sample data fixtures (sample_events, schedule_request)

### Phase 2: Integration Tests
1. Create `tests/integration/` directory
2. Add tests for Create mode workflow
3. Add tests for Update mode workflow
4. Add tests for Delete mode workflow
5. Add tests for Import mode workflow
6. Add mode transition tests

### Phase 3: Coverage Enforcement
1. Configure `pytest.ini` with coverage settings
2. Add coverage threshold to CI/CD workflow
3. Add HTML report generation step

---

## File Structure

```
tests/
├── conftest.py                 # Base fixtures (qapp, qtbot)
├── fixtures/
│   ├── __init__.py
│   ├── mock_api.py            # Mock GoogleApi fixture
│   └── sample_data.py         # Sample event fixtures
├── integration/
│   ├── __init__.py
│   ├── test_create_mode.py
│   ├── test_update_mode.py
│   ├── test_delete_mode.py
│   ├── test_import_mode.py
│   └── test_mode_transitions.py
├── test_*.py                  # Existing unit tests (unchanged)
```

---

## Dependencies

- `pytest` (already in requirements.txt)
- `pytest-cov` (already in requirements.txt)
- `responses` (new - for HTTP mocking)

---

## Existing Test Audit

Conducted a comprehensive audit of the existing test suite to inform the comprehensive testing initiative.

### Current Test Metrics

| Metric | Value |
|--------|-------|
| Test Files | 32 |
| Total Lines | ~8,365 |
| Tests Collected | 81 (from working files) |
| Collection Errors | 22 (PySide6 not installed in environment) |

### Test File Distribution

| Category | Files | Purpose |
|----------|-------|---------|
| Worker tests | 3 | EventCreationWorker, DeleteWorker, UpdateWorker |
| UndoManager tests | 3 | State machine, persistence, batch operations |
| UI tests | 12 | Batch selector, mode transitions, modals, dates |
| Import tests | 5 | Fetch, batching, shutdown handling |
| Validation tests | 2 | Date/time parsing, schedule building |
| Service tests | 1 | GoogleApi dataclasses |

### Existing Fixtures (conftest.py)

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `qapp` | session | QApplication instance for Qt tests |
| `qtbot` | function | Custom QtBot with `addWidget()`, `waitSignal()` |

### Test Quality Assessment

| Module | Size | Quality Notes |
|--------|------|---------------|
| `test_event_creation_worker.py` | 17.8KB | Good - initialization, execution, signals, email |
| `test_undo_manager.py` | 16KB | Good - state machine, persistence, edge cases |
| `test_gui_batch_selector.py` | 29KB | Extensive UI testing with qtbot |
| `test_workers.py` | 12.4KB | Good - worker coverage |
| `test_validation.py` | 1.7KB | **Minimal** - only 5 tests, edge cases missing |

### Issues Identified

**1. pytest-cov in pytest.ini but not installed**
```ini
# pytest.ini references coverage but package not installed
addopts = --cov=app --cov=tests --cov-report=term-missing
```

**2. Collection errors due to PySide6** - All 22 errors caused by PySide6 not installed in audit environment. Tests require network to install packages.

**3. Python-level mocking only** - Tests mock at class level (`MagicMock`) rather than HTTP level. Cannot catch serialization/deserialization bugs.

**4. No HTTP-level integration** - `responses` library not used; Google API calls would require live credentials.

**5. Validation module undertrained** - Only 5 tests covering validation module.

### Existing Test Patterns

```python
# Current pattern: Python-level mocking
@pytest.fixture
def mock_api():
    api = MagicMock()
    api.delete_event = MagicMock()
    api.create_event = MagicMock()
    api.send_email = MagicMock()
    return api

# Signal testing with custom QtBot
def test_emits_finished(self, qtbot, worker):
    waiter = qtbot.waitSignal(worker.finished, timeout=2000)
    worker.run()
    assert waiter.called
```

### Recommendations from Audit

1. **Fix pytest.ini** - Remove coverage flags if pytest-cov not installed, or ensure it's installed
2. **Add responses library** - Enable HTTP-level mocking for API serialization testing
3. **Expand validation tests** - Only 5 tests currently, missing edge cases (empty input, invalid dates)
4. **Create shared fixtures** - `mock_api`, `sample_events` appear in multiple files; centralize in conftest.py

### Alignment with comprehensive-testing initiative

The existing audit findings directly inform the planned improvements:

| Audit Finding | Comprehensive-Testing Action |
|---------------|------------------------------|
| No HTTP mocking | Add `responses` library, `tests/fixtures/mock_api.py` |
| Python-level only | Create `tests/fixtures/http_mock.py` for HTTP-level interception |
| Minimal validation coverage | Add `tests/integration/test_create_mode.py` with validation edge cases |
| Duplicated fixtures | Enhance `conftest.py` with `mock_api`, `sample_events` fixtures |
| pytest-cov issue | Fix `pytest.ini` coverage configuration as part of setup |