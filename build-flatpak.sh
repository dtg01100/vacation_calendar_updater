#!/bin/bash
# Build and install the Vacation Calendar Updater Flatpak

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLATPAK_DIR="${SCRIPT_DIR}/flatpak"
BUILD_DIR="${SCRIPT_DIR}/build"
SOURCE_DIR="/tmp/vacation-flatpak-build"

# Verify flatpak-builder is installed
if ! command -v flatpak-builder &> /dev/null; then
    echo "Error: flatpak-builder is not installed"
    exit 1
fi

echo "=== Preparing Flatpak build ==="

# Clean previous build artifacts
rm -rf "$BUILD_DIR" "${SCRIPT_DIR}/.flatpak-builder" 2>/dev/null || true
mkdir -p "$BUILD_DIR"

# Create clean source directory for build
rm -rf "$SOURCE_DIR" 2>/dev/null || true
mkdir -p "$SOURCE_DIR"

# Copy source files (excluding test files and build artifacts)
echo "Copying source files..."
rsync -av --exclude='*.pyc' --exclude='__pycache__' --exclude='*.pyo' \
    --exclude='tests' --exclude='.git' --exclude='build' \
    --exclude='.flatpak-builder' --exclude='.venv' \
    "${SCRIPT_DIR}/" "$SOURCE_DIR/" 2>/dev/null || true

# Ensure wheel files are in the flatpak directory
if [ -d "${SCRIPT_DIR}/flatpak" ]; then
    cp "${SCRIPT_DIR}/flatpak"/*.whl "$SOURCE_DIR/flatpak/" 2>/dev/null || true
    cp "${SCRIPT_DIR}/flatpak"/*.tar.gz "$SOURCE_DIR/flatpak/" 2>/dev/null || true
fi

# Ensure desktop file is in the source root
if [ -f "${FLATPAK_DIR}/com.github.dtg01100.vacation_calendar_updater.desktop" ]; then
    cp "${FLATPAK_DIR}/com.github.dtg01100.vacation_calendar_updater.desktop" "$SOURCE_DIR/"
fi

echo "=== Building Flatpak ==="
echo "This may take several minutes..."

# Build and install the Flatpak
flatpak-builder --user --install --force-clean \
    "$BUILD_DIR" \
    "${FLATPAK_DIR}/com.github.dtg01100.vacation_calendar_updater.json"

echo ""
echo "=== Flatpak build complete ==="
echo ""
echo "To run the application:"
echo "  flatpak run com.github.dtg01100.vacation_calendar_updater"
echo ""
echo "To uninstall:"
echo "  flatpak uninstall --user com.github.dtg01100.vacation_calendar_updater"
