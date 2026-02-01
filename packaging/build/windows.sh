#!/bin/bash
# ExCut Windows EXE Automation Script (via Docker)
# Should be run from the project root: ./packaging/build/windows.sh

set -e

# 1. Setup paths
BASE_DIR=$(pwd)
VERSION="v0.8" 
ARCH="x86_64" 
PACKAGING_DIR="$BASE_DIR/packaging"

# Artifact organization
WORKSPACE_DIR="$BASE_DIR/build"
WIN_BUILD_DIR="$WORKSPACE_DIR/windows_build"
WIN_DIST_DIR="$WORKSPACE_DIR/windows_dist"
DIST_DIR="$BASE_DIR/dist"
OUT_NAME="ExCut-$ARCH-$VERSION.exe"
OUT_PATH="$DIST_DIR/$OUT_NAME"

echo "🚀 Starting ExCut $VERSION Windows Build Process (via Docker/Podman)..."

# 2. Ensure a container engine exists
if command -v docker >/dev/null 2>&1; then
    DOCKER_CMD="docker"
elif command -v podman >/dev/null 2>&1; then
    DOCKER_CMD="podman"
else
    echo "❌ Error: Neither 'docker' nor 'podman' found."
    echo "Please install Docker (or Podman on Fedora) to use the Windows cross-compilation script."
    exit 1
fi

# 3. Clean previous specific build files
echo "🧹 Cleaning previous build artifacts..."
rm -rf "$WIN_BUILD_DIR" "$WIN_DIST_DIR" 
rm -f "$OUT_PATH"
mkdir -p "$WIN_BUILD_DIR" "$WIN_DIST_DIR" "$DIST_DIR"

# 4. Running PyInstaller via Docker/Podman
echo "🛠️ Building EXE with PyInstaller in $DOCKER_CMD..."
$DOCKER_CMD run --rm --network host \
    -v "$BASE_DIR:/src:Z" \
    -e BUILD_MODE=onefile \
    docker.io/batonogov/pyinstaller-windows \
    "python -m pip install Pillow && python -m pip install -r requirements.txt && pyinstaller --workpath build/windows_build --distpath build/windows_dist packaging/ExCut.spec"

# 5. Finalize output
echo "📂 Finalizing executable..."
# In onefile mode, the EXE is directly in distpath, not in a subdirectory.
GENERATED_EXE=$(find "$WIN_DIST_DIR" -maxdepth 1 -name "*.exe" | head -n 1)

if [ -f "$GENERATED_EXE" ]; then
    cp "$GENERATED_EXE" "$OUT_PATH"
    echo "✅ Build Complete: $OUT_PATH"
else
    echo "❌ Error: Could not find generated .exe in $WIN_DIST_DIR"
    exit 1
fi
