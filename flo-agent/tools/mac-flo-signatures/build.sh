#!/bin/bash
# Build the Flo Signatures Mac .app bundle from source.
# Regenerates Contents/Resources/flo-icon.icns from the Flo badge PNG,
# chmod +x's the launcher, and prints the install instructions.
#
# Idempotent. Safe to re-run after editing the Info.plist, the launcher
# script, or the icon source.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/Flo Signatures.app"
CONTENTS="$APP/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
LAUNCHER="$MACOS/flo-signatures-launcher"
INFO="$CONTENTS/Info.plist"
ICNS="$RESOURCES/flo-icon.icns"
ICONSET="$(mktemp -d)/flo-signatures.iconset"
ICON_SRC="${FLO_BADGE_PNG:-$HERE/../../apps/desktop/public/flo-badge.png}"

# ── Sanity checks ──────────────────────────────────────────────────────────
if [ ! -f "$ICON_SRC" ]; then
    echo "error: Flo badge PNG not found at $ICON_SRC" >&2
    echo "       set FLO_BADGE_PNG to override" >&2
    exit 1
fi

# ── Launcher permissions ───────────────────────────────────────────────────
chmod +x "$LAUNCHER"

# ── Regenerate .icns from the PNG ──────────────────────────────────────────
mkdir -p "$ICONSET"
trap 'rm -rf "$ICONSET"' EXIT

for s in 16 32 64 128 256 512; do
    sips -z "$s" "$s" "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
done
# @2x variants
sips -z 32   32   "$ICON_SRC" --out "$ICONSET/icon_16x16@2x.png"    >/dev/null
sips -z 64   64   "$ICON_SRC" --out "$ICONSET/icon_32x32@2x.png"    >/dev/null
sips -z 256  256  "$ICON_SRC" --out "$ICONSET/icon_128x128@2x.png"  >/dev/null
sips -z 512  512  "$ICON_SRC" --out "$ICONSET/icon_256x256@2x.png"  >/dev/null
sips -z 1024 1024 "$ICON_SRC" --out "$ICONSET/icon_512x512@2x.png"  >/dev/null

iconutil -c icns "$ICONSET" -o "$ICNS"

echo "✓ rebuilt $APP"
echo
echo "Install (Ashley-facing):"
echo "  cp -R \"$APP\" ~/Applications/"
echo
echo "After install, launch once from Finder so macOS records the bundle id."
