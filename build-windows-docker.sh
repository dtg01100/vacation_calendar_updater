#!/bin/bash
set -e

# Build Windows executable using batonogov/pyinstaller Docker container
# The container's entrypoint handles everything:
# 1. Installs requirements.txt
# 2. Runs pyinstaller on the .spec file

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building Windows executable ==="
echo "Using batonogov/pyinstaller-windows container"

docker run --rm -v "$SCRIPT_DIR:/src/" batonogov/pyinstaller-windows:latest

echo ""
echo "=== Build complete ==="
ls -lh dist/VacationCalendarUpdater.exe 2>/dev/null || echo "Check dist/ directory"
