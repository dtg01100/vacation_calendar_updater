#!/bin/bash
# Run the Vacation Calendar Updater GUI application
# Usage: ./run.sh [options]
# Options:
#   --help      Show this help message
#   --no-venv   Don't create/use virtual environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
NO_VENV=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help)
            echo "Vacation Calendar Updater GUI Launcher"
            echo ""
            echo "Usage: ./run.sh [options]"
            echo ""
            echo "Options:"
            echo "  --help      Show this help message"
            echo "  --no-venv   Don't create/use virtual environment (use system Python)"
            echo ""
            exit 0
            ;;
        --no-venv)
            NO_VENV=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set up Python environment
if [ "$NO_VENV" = false ]; then
    # Check if venv exists and is valid
    VENV_VALID=false
    if [ -f "$VENV_DIR/bin/python" ]; then
        # Test if venv python is actually usable
        if "$VENV_DIR/bin/python" -c "import sys" 2>/dev/null; then
            VENV_VALID=true
        fi
    fi
    
    if [ "$VENV_VALID" = false ]; then
        # Recreate venv if invalid
        echo "📦 Setting up virtual environment..."
        rm -rf "$VENV_DIR"
        if python3 -m venv "$VENV_DIR"; then
            echo "✅ Virtual environment created"
        else
            echo "❌ Failed to create virtual environment"
            exit 1
        fi
        
        echo "📥 Installing dependencies..."
        if "$VENV_DIR/bin/pip" install -q -r requirements.txt; then
            echo "✅ Dependencies installed."
        else
            echo "❌ Failed to install dependencies"
            exit 1
        fi
    else
        # Verify PySide6 is installed
        if ! "$VENV_DIR/bin/python" -c "import PySide6" 2>/dev/null; then
            echo "📥 Installing missing dependencies..."
            "$VENV_DIR/bin/pip" install -q -r requirements.txt
            echo "✅ Dependencies installed."
        fi
    fi
fi

# Change to project directory
cd "$SCRIPT_DIR"

# Run the application
echo "🚀 Starting Vacation Calendar Updater..."

# Determine which Python to use
if [ "$NO_VENV" = false ]; then
    PYTHON_CMD="${VENV_DIR}/bin/python"
else
    PYTHON_CMD="python"
fi

# Use offscreen rendering only if no display is available
if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
    export QT_QPA_PLATFORM=offscreen
fi

"$PYTHON_CMD" -m app.__main__
