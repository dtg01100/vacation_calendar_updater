#!/bin/bash
set -e

# Build AppImage for Vacation Calendar Updater
# Uses PyInstaller + AppImage tool

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building AppImage ==="

# Clean up and create AppDir structure
rm -rf "$SCRIPT_DIR/AppDir"
mkdir -p "$SCRIPT_DIR/AppDir/usr/bin"
mkdir -p "$SCRIPT_DIR/AppDir/usr/lib"
mkdir -p "$SCRIPT_DIR/AppDir/usr/share/icons/hicolor/256x256/apps"

# Check dependencies
if [ ! -f "$SCRIPT_DIR/appimagetool" ]; then
    echo "Installing appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O "$SCRIPT_DIR/appimagetool"
    chmod +x "$SCRIPT_DIR/appimagetool"
fi
APPIMAGETOOL="$SCRIPT_DIR/appimagetool"

# Check if we have a pre-built executable in dist/
if [ -f "$SCRIPT_DIR/dist/VacationCalendarUpdater" ]; then
    echo "Using pre-built executable from dist/"
    cp "$SCRIPT_DIR/dist/VacationCalendarUpdater" "$SCRIPT_DIR/AppDir/usr/bin/"
else
    echo "No pre-built executable found. Run build-linux.sh first."
    exit 1
fi

# Create desktop file
cat > "$SCRIPT_DIR/AppDir/VacationCalendarUpdater.desktop" << 'DESKTOP'
[Desktop Entry]
Name=Vacation Calendar Updater
Comment=Manage vacation calendar events in Google Calendar
Exec=AppRun
Icon=VacationCalendarUpdater
Type=Application
Categories=Office;Calendar;
DESKTOP
cp "$SCRIPT_DIR/AppDir/VacationCalendarUpdater.desktop" "$SCRIPT_DIR/AppDir/.desktop"

# Use existing icon from flatpak/ directory instead of creating a new one
if [ -f "flatpak/icon-256x256.png" ]; then
    cp "flatpak/icon-256x256.png" "AppDir/VacationCalendarUpdater.png"
    echo "Using existing icon from flatpak/icon-256x256.png"
else
    echo "Warning: No icon found in flatpak/ directory"
fi

# Create placeholder icon for .DirIcon
printf '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4\x00\x00\x00\x00IEND\xaeB`\x82' > "$SCRIPT_DIR/AppDir/.DirIcon"
cp "$SCRIPT_DIR/AppDir/.DirIcon" "$SCRIPT_DIR/AppDir/usr/share/icons/hicolor/256x256/apps/VacationCalendarUpdater.png" 2>/dev/null || true

# Create AppRun script
cat > "$SCRIPT_DIR/AppDir/AppRun" << 'APPRUN'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/VacationCalendarUpdater" "$@"
APPRUN
chmod +x "$SCRIPT_DIR/AppDir/AppRun"

# Create dist directory
mkdir -p "$SCRIPT_DIR/dist"

# Copy client_secret.json if it exists
if [ -f "client_secret.json" ]; then
    cp client_secret.json "$SCRIPT_DIR/AppDir/usr/bin/"
fi

# Create AppImage
echo "Creating AppImage..."
ARCH=x86_64 "$APPIMAGETOOL" "$SCRIPT_DIR/AppDir" "$SCRIPT_DIR/dist/VacationCalendarUpdater.AppImage"

echo ""
echo "=== Build complete ==="
ls -lh "$SCRIPT_DIR/dist/VacationCalendarUpdater.AppImage" && echo "Output: dist/VacationCalendarUpdater.AppImage" || echo "Build failed"