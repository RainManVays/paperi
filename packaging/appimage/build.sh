#!/bin/bash
# Builds dist/PeriPrint-x86_64.AppImage. Needs only Docker on the host —
# see docs/appimage-packaging-guide.md for the reasoning behind each step.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
IMAGE_TAG="periprint-appimage-builder"
DIST_DIR="$REPO_ROOT/dist/appimage"
APPIMAGETOOL="$HERE/.cache/appimagetool-x86_64.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"

command -v docker >/dev/null || {
    echo "Docker is required to build the AppImage (for a reproducible, old-glibc build environment)." >&2
    exit 1
}

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

echo "==> Building Docker build image ($IMAGE_TAG)"
docker build -t "$IMAGE_TAG" -f "$HERE/Dockerfile" "$HERE"

echo "==> Building frozen app with PyInstaller (inside Docker)"
docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$REPO_ROOT:/repo" \
    -w /repo \
    -e HOME=/tmp \
    "$IMAGE_TAG" \
    bash -c '
        set -euo pipefail
        python3.12 -m venv /tmp/build-venv
        /tmp/build-venv/bin/pip install --quiet --upgrade pip
        /tmp/build-venv/bin/pip install --quiet -e . pyinstaller
        /tmp/build-venv/bin/pyinstaller packaging/appimage/periprint.spec \
            --distpath /repo/dist/appimage/pyinstaller-dist \
            --workpath /tmp/pyinstaller-work \
            --noconfirm
    '

echo "==> Assembling AppDir"
APPDIR="$DIST_DIR/PeriPrint.AppDir"
mkdir -p "$APPDIR/usr/bin"
cp -r "$DIST_DIR/pyinstaller-dist/periprint" "$APPDIR/usr/bin/periprint"
install -m755 "$HERE/AppRun" "$APPDIR/AppRun"
install -m644 "$HERE/periprint.desktop" "$APPDIR/periprint.desktop"
install -m644 "$HERE/periprint.png" "$APPDIR/periprint.png"

if [ ! -x "$APPIMAGETOOL" ]; then
    echo "==> Downloading appimagetool"
    mkdir -p "$HERE/.cache"
    curl -fsSL -o "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
    chmod +x "$APPIMAGETOOL"
fi

echo "==> Packing AppImage"
VERSION="$(cd "$REPO_ROOT" && source .venv/bin/activate 2>/dev/null && python -c 'import periprint; print(periprint.__version__)' 2>/dev/null || echo dev)"
(
    cd "$DIST_DIR"
    ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$REPO_ROOT/dist/PeriPrint-x86_64.AppImage"
)

echo "==> Done: dist/PeriPrint-x86_64.AppImage (version: $VERSION)"
