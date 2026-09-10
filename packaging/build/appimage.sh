#!/bin/bash
# ExCut AppImage Automation Script
# Should be run from the project root: ./packaging/build/appimage.sh

set -e

# 1. Setup paths
BASE_DIR=$(pwd)
VERSION="v0.27" # Initial placeholder, will be bumped
ARCH=$(uname -m)
PACKAGING_DIR="$BASE_DIR/packaging"
BUILD_TOOLS_DIR="$PACKAGING_DIR/build"

# Artifact organization
WORKSPACE_DIR="$BASE_DIR/build"
PYBUILD_DIR="$WORKSPACE_DIR/pyinstaller_build"
PYDIST_DIR="$WORKSPACE_DIR/pyinstaller_dist"
APPDIR="$WORKSPACE_DIR/ExCut.AppDir"
DIST_DIR="$BASE_DIR/dist"
OUT_NAME="ExCut-$ARCH-$VERSION.AppImage"
OUT_PATH="$DIST_DIR/$OUT_NAME"

TOOL_NAME="appimagetool-x86_64.AppImage"
TOOL_PATH="$BUILD_TOOLS_DIR/$TOOL_NAME"

echo "🚀 Starting ExCut $VERSION ($ARCH) AppImage Build Process..."

# 2. Ensure appimagetool exists
if [ ! -f "$TOOL_PATH" ] && ! command -v appimagetool >/dev/null 2>&1; then
    echo "⬇️ Downloading appimagetool..."
    mkdir -p "$BUILD_TOOLS_DIR"
    curl -L -o "$TOOL_PATH" "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$TOOL_PATH"
fi

# 3. Clean previous specific build files (leaving other files in build/dist untouched)
echo "🧹 Cleaning previous build artifacts..."
rm -rf "$PYBUILD_DIR" "$PYDIST_DIR" "$APPDIR"
rm -f "$OUT_PATH"
mkdir -p "$PYBUILD_DIR" "$PYDIST_DIR" "$DIST_DIR"

# 4. Running PyInstaller
echo "🛠️ Building binaries with PyInstaller..."
BUILD_MODE=onedir pyinstaller --workpath "$PYBUILD_DIR" \
            --distpath "$PYDIST_DIR" \
            "$PACKAGING_DIR/ExCut.spec"

# 5. Prepare AppDir
echo "📂 Preparing AppDir structure..."
mkdir -p "$APPDIR"
cp -r "$PYDIST_DIR/ExCut/"* "$APPDIR/"
# If one-file mode is used, adjust the above copy:
# cp "$PYDIST_DIR/ExCut" "$APPDIR/"

cp "$PACKAGING_DIR/AppRun" "$APPDIR/"
cp "$PACKAGING_DIR/excut.desktop" "$APPDIR/"
cp "$PACKAGING_DIR/icon.png" "$APPDIR/"

chmod +x "$APPDIR/AppRun"

# 6. Build AppImage
echo "📦 Generating AppImage..."
if command -v appimagetool >/dev/null 2>&1; then
    appimagetool "$APPDIR" "$OUT_PATH"
else
    "$TOOL_PATH" "$APPDIR" "$OUT_PATH"
fi

echo "✅ Build Complete: $OUT_PATH"
