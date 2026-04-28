#!/bin/bash
# Build the Vacation Calendar Updater Flatpak bundle

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLATPAK_DIR="${SCRIPT_DIR}/flatpak"
BUILD_DIR="${SCRIPT_DIR}/build"
REPO_DIR="${BUILD_DIR}/repo"
BUNDLE_FILE="${SCRIPT_DIR}/vacation-calendar-updater.flatpak"
PIP_GENERATOR="${SCRIPT_DIR}/flatpak-builder-tools/pip/flatpak-pip-generator"
TEMP_DIR="${BUILD_DIR}/source-temp"

BUILD_MODE="${1:-bundle}"

verify_flatpak_builder() {
	if ! command -v flatpak-builder &>/dev/null; then
		echo "Error: flatpak-builder is not installed"
		echo "Install with: flatpak install flathub flatpak-builder"
		exit 1
	fi
}

prepare_dependencies() {
	echo "=== Ensuring pip generator build-only dependencies ==="
	PYTHON_BIN="python3"
	if ! python3 -c "import requirements" >/dev/null 2>&1; then
		VENV_DIR="${BUILD_DIR}/.flatpak-tools-venv"
		python3 -m venv "$VENV_DIR"
		"${VENV_DIR}/bin/python" -m pip install --upgrade pip >/dev/null
		"${VENV_DIR}/bin/python" -m pip install 'requirements-parser>=0.11,<1.0' 'packaging>=23.0' >/dev/null
		PYTHON_BIN="${VENV_DIR}/bin/python"
	fi

	if [ -f "${FLATPAK_DIR}/pypi-dependencies.json" ]; then
		echo "=== Using existing pypi-dependencies.json ==="
	else
		echo "=== Generating PyPI dependencies ==="
		PIP_ONLY_BINARY=:all: "$PYTHON_BIN" "$PIP_GENERATOR" \
			--requirements="${FLATPAK_DIR}/requirements-runtime.txt" \
			--output="${FLATPAK_DIR}/pypi-dependencies.json"
	fi
}

create_source_tarball() {
	echo "=== Creating source tarball ==="
	mkdir -p "$TEMP_DIR"
	rsync -av --exclude='.git' --exclude='.flatpak-builder' --exclude='build' \
		--exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
		--exclude='.mypy_cache' --exclude='.vscode' --exclude='.idea' \
		--exclude='*.egg-info' --exclude='.eggs' --exclude='dist' \
		--exclude='*.whl' --exclude='containerhome' --exclude='.devcontainer.json' \
		--exclude='Dockerfile' --exclude='.gitmodules' \
		"${SCRIPT_DIR}/" "$TEMP_DIR/" --include='app/***' --include='client_secret.json' --include='pyproject.toml' --include='flatpak/***' --include='run.sh' --exclude='*'
	tar -czf "${FLATPAK_DIR}/vacation-calendar-updater.tar.gz" -C "$TEMP_DIR" .
	cp "${FLATPAK_DIR}/vacation-calendar-updater.tar.gz" "${SCRIPT_DIR}/"
}

build_repo() {
	echo "=== Building Flatpak repo ==="
	echo "This may take several minutes..."

	mkdir -p "$REPO_DIR"
	flatpak-builder --repo="$REPO_DIR" --force-clean \
		"$BUILD_DIR/app" \
		"${FLATPAK_DIR}/com.github.dtg01100.vacation_calendar_updater.json"
}

build_bundle() {
	echo "=== Creating Flatpak bundle ==="
	flatpak build-bundle "$REPO_DIR" "$BUNDLE_FILE" \
		com.github.dtg01100.vacation_calendar_updater
}

install_local() {
	echo "=== Installing Flatpak locally ==="
	flatpak-builder --user --install --force-clean \
		"$BUILD_DIR/app" \
		"${FLATPAK_DIR}/com.github.dtg01100.vacation_calendar_updater.json"
}

cleanup() {
	rm -rf "$TEMP_DIR"
}

main() {
	verify_flatpak_builder

	echo "=== Preparing Flatpak build ==="
	rm -rf "$BUILD_DIR" "${SCRIPT_DIR}/.flatpak-builder" 2>/dev/null || true
	mkdir -p "$BUILD_DIR"

	prepare_dependencies
	create_source_tarball
	build_repo

	case "$BUILD_MODE" in
	bundle)
		build_bundle
		cleanup
		echo ""
		echo "=== Flatpak bundle built successfully ==="
		echo "Bundle location: $BUNDLE_FILE"
		echo ""
		echo "To install the bundle:"
		echo "  flatpak install $BUNDLE_FILE"
		echo ""
		echo "To uninstall after installation:"
		echo "  flatpak uninstall com.github.dtg01100.vacation_calendar_updater"
		;;
	install)
		install_local
		cleanup
		echo ""
		echo "=== Flatpak installed successfully ==="
		echo ""
		echo "To run the application:"
		echo "  flatpak run com.github.dtg01100.vacation_calendar_updater"
		echo ""
		echo "To uninstall:"
		echo "  flatpak uninstall --user com.github.dtg01100.vacation_calendar_updater"
		;;
	*)
		echo "Usage: $0 [bundle|install]"
		echo "  bundle (default) - Build a distributable .flatpak file"
		echo "  install          - Build and install locally"
		exit 1
		;;
	esac
}

main
