#!/bin/bash
set -e

# Build Windows executable using batonogov/pyinstaller Docker container
# The container's entrypoint handles everything:
# 1. Installs requirements.txt
# 2. Runs pyinstaller on the .spec file

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building Windows executable ==="

# Check if client_secret.json exists, create placeholder if not
if [ ! -f "client_secret.json" ]; then
	echo "Warning: client_secret.json not found, creating placeholder..."
	cat >client_secret.json <<'EOF'
{
  "web": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "project_id": "YOUR_PROJECT_ID",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": ["http://localhost:8080"]
  }
}
EOF
	echo "Created placeholder client_secret.json - replace with your actual credentials"
fi

echo "Using batonogov/pyinstaller-windows container"

docker run --rm -v "$SCRIPT_DIR:/src/" batonogov/pyinstaller-windows:latest

echo ""
echo "=== Build complete ==="
ls -lh dist/VacationCalendarUpdater.exe 2>/dev/null && echo "Output: dist/VacationCalendarUpdater.exe" || echo "Check dist/ directory"
