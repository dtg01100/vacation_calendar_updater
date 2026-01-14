# Import Feature Iteration Guide

## Quick Testing
Run all import tests without full UI:
```bash
bash test_import.sh
```

This runs:
- **10 batching logic tests** (event grouping, gap detection, field validation)
- **1 fetch worker test** (API integration, datetime handling)
- **3 shutdown tests** (thread lifecycle, app quit handling)

## Test Files by Purpose

### `tests/test_import_batching.py` (10 tests)
**Use when:** Iterating on batching/grouping logic
- Tests event grouping by summary
- Tests gap detection (>3 days = separate batch)
- Tests handling of missing fields
- Fast, no external dependencies

**Run:**
```bash
.venv/bin/python -m pytest tests/test_import_batching.py -v
```

### `tests/test_import_fetch_worker.py` (1 test)
**Use when:** Testing the ImportFetchWorker with mocked API
- Tests datetime parsing (dt alias)
- Tests calendar_service() usage
- Tests fetch → grouping pipeline

**Run:**
```bash
.venv/bin/python -m pytest tests/test_import_fetch_worker.py -v
```

### `tests/test_import_shutdown.py` (3 tests)
**Use when:** Ensuring import thread cleanup and Qt shutdown
- Tests import_thread cleanup
- Tests aboutToQuit signal hook
- Tests destructor safety

**Run:**
```bash
.venv/bin/python -m pytest tests/test_import_shutdown.py -v
```

## Debugging Workflow

### If batching produces wrong results:
```bash
# Add print statements in test_import_batching.py
# Run specific test:
.venv/bin/python -m pytest tests/test_import_batching.py::TestImportBatchingLogic::test_group_events_with_gap_separate_batches -vv
```

### If fetch crashes:
```bash
# Check the test failure and mock the API differently:
.venv/bin/python -m pytest tests/test_import_fetch_worker.py -vv --tb=long
```

### If import UI crashes:
```bash
# Run full app and check console for errors
./run.sh

# Or run the broader test suite to catch integration issues:
.venv/bin/python -m pytest tests/test_mode_transitions.py tests/test_ui_modals.py -q
```

## Manual Testing Checklist

1. **Start app:**
   ```bash
   ./run.sh
   ```

2. **Switch to Import mode** → import controls frame should be visible

3. **Click "Fetch from Calendar"** → should fetch and show batch list (or error if no events)

4. **Select/deselect batches** → checkbox state should update

5. **Click "Import Selected Batches"** → should add to undo history

6. **Close app** → no "QThread destroyed" errors

## Common Issues & Fixes

| Issue | Check | Test |
|-------|-------|------|
| "QThread destroyed" crash | Thread cleanup in `closeEvent`/`__del__` | `test_import_shutdown.py` |
| `'GoogleApi' has no attribute 'service'` | Using `calendar_service()` method | `test_import_fetch_worker.py` |
| `name 'dt' is not defined` | Import `datetime as dt` in main_window | `test_import_fetch_worker.py` |
| Wrong batch grouping | Gap threshold and summary matching | `test_import_batching.py` |
| UI not visible | `import_controls_frame.setVisible(True)` in `_switch_mode` | Manual |

## Add New Tests

Example of adding a test for new batching logic:
```python
# In tests/test_import_batching.py

def test_new_batching_feature(self):
    """Describe what the test does."""
    items = [
        create_sample_event("e1", "Event", "2024-01-01", "2024-01-02"),
    ]
    batches = group_events_into_batches(items, "cal_001")
    
    # Assert expected behavior
    assert len(batches) == 1
    assert batches[0]["event_count"] == 1
```

Then run:
```bash
.venv/bin/python -m pytest tests/test_import_batching.py::TestImportBatchingLogic::test_new_batching_feature -v
```
