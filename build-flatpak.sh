#!/bin/bash
# Build and install the Vacation Calendar Updater Flatpak

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLATPAK_DIR="${SCRIPT_DIR}/flatpak"
BUILD_DIR="${SCRIPT_DIR}/build"
PIP_GENERATOR="${SCRIPT_DIR}/flatpak-builder-tools/pip/flatpak-pip-generator"
TEMP_DIR="${BUILD_DIR}/source-temp"

# Verify flatpak-builder is installed
if ! command -v flatpak-builder &>/dev/null; then
	echo "Error: flatpak-builder is not installed"
	exit 1
fi

echo "=== Preparing Flatpak build ==="

# Clean previous build artifacts
rm -rf "$BUILD_DIR" "${SCRIPT_DIR}/.flatpak-builder" 2>/dev/null || true
mkdir -p "$BUILD_DIR"

echo "=== Ensuring pip generator build-only dependencies ==="
# Use a temporary virtual environment for build-only Python deps to avoid
# polluting the app runtime requirements. This is only used to run
# flatpak-builder-tools' flatpak-pip-generator which requires
# 'requirements-parser' and 'packaging'.
PYTHON_BIN="python3"
if ! python3 -c "import requirements" >/dev/null 2>&1; then
	VENV_DIR="${BUILD_DIR}/.flatpak-tools-venv"
	python3 -m venv "$VENV_DIR"
	"${VENV_DIR}/bin/python" -m pip install --upgrade pip >/dev/null
	"${VENV_DIR}/bin/python" -m pip install 'requirements-parser>=0.11,<1.0' 'packaging>=23.0' >/dev/null
	PYTHON_BIN="${VENV_DIR}/bin/python"
fi

echo "=== Generating PyPI dependencies ==="
# Generate pypi-dependencies.json using flatpak-pip-generator
"$PYTHON_BIN" "$PIP_GENERATOR" \
	--requirements="${FLATPAK_DIR}/requirements-runtime.txt" \
	--output="${FLATPAK_DIR}/pypi-dependencies.json"

echo "=== Creating source tarball ==="
# Create a clean tarball without git files
mkdir -p "$TEMP_DIR"
rsync -av --exclude='.git' --exclude='.flatpak-builder' --exclude='build' \
	--exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
	--exclude='.mypy_cache' --exclude='.vscode' --exclude='.idea' \
	--exclude='*.egg-info' --exclude='.eggs' --exclude='dist' \
	--exclude='*.whl' --exclude='containerhome' --exclude='.devcontainer.json' \
	--exclude='Dockerfile' --exclude='.gitmodules' \
	"${SCRIPT_DIR}/" "$TEMP_DIR/" --include='app/***' --include='client_secret.json' --include='pyproject.toml' --include='flatpak/***' --include='run.sh' --exclude='*'
tar -czf "${FLATPAK_DIR}/vacation-calendar-updater.tar.gz" -C "$TEMP_DIR" .

# Copy tarball to a location flatpak-builder can find
cp "${FLATPAK_DIR}/vacation-calendar-updater.tar.gz" "${SCRIPT_DIR}/"

echo "=== Building Flatpak ==="
echo "This may take several minutes..."

# Build and install the Flatpak
flatpak-builder --user --install --force-clean \
	"$BUILD_DIR" \
	"${FLATPAK_DIR}/com.github.dtg01100.vacation_calendar_updater.json"

# Clean up temporary files
rm -rf "$TEMP_DIR"

echo ""
echo "=== Flatpak build complete ==="
echo ""
echo "To run the application:"
echo "  flatpak run com.github.dtg01100.vacation_calendar_updater"
echo ""
echo "To uninstall:"
echo "  flatpak uninstall --user com.github.dtg01100.vacation_calendar_updater"
