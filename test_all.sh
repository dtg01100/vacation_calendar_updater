#!/usr/bin/env bash
# Full test suite with emphasis on import feature

echo "🧪 Running full test suite..."
echo ""

# Core tests (quick)
echo "📋 Core tests (mode transitions, UI, modals):"
.venv/bin/python -m pytest tests/test_mode_transitions.py tests/test_gui_batch_selector.py tests/test_ui_modals.py -q --tb=line
CORE_EXIT=$?
echo ""

# Import-specific tests
echo "📥 Import feature tests:"
bash test_import.sh
IMPORT_EXIT=$?
echo ""

# Summary
if [ $CORE_EXIT -eq 0 ] && [ $IMPORT_EXIT -eq 0 ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ Some tests failed"
    exit 1
fi
