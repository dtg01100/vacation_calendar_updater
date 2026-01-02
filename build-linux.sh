#!/bin/bash
set -e

# Build Linux executable using PyInstaller
# Uses the same app.spec file as Windows build

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building Linux executable ==="

# Create dist directory if it doesn't exist
mkdir -p dist

# Build using PyInstaller via uv (ensures correct dependencies)
uv run pyinstaller --distpath dist app.spec

echo ""
echo "=== Build complete ==="
ls -lh dist/VacationCalendarUpdater 2>/dev/null && echo "Output: dist/VacationCalendarUpdater" || echo "Build failed - check errors above"
