#!/bin/bash
# Run the Vacation Calendar Updater application

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
	echo "Creating virtual environment..."
	uv venv "$VENV_DIR"
	source "$VENV_DIR/bin/activate"
	echo "Installing dependencies..."
	uv pip install pyside6 httplib2 python-dateutil validate-email \
		google-api-python-client google-auth requests protobuf \
		oauth2client rfc3339
	echo "Dependencies installed."
else
	source "$VENV_DIR/bin/activate"
	# Verify PySide6 is installed
	if ! python -c "import PySide6" 2>/dev/null; then
		echo "Installing missing dependencies..."
		uv pip install pyside6 httplib2 python-dateutil validate-email \
			google-api-python-client google-auth requests protobuf \
			oauth2client rfc3339
		echo "Dependencies installed."
	fi
fi

# Run the application
echo "Starting Vacation Calendar Updater..."
python -m app.ui.main_window
