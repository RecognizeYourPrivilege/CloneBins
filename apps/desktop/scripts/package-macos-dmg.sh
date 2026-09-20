#!/usr/bin/env bash
# Copy a clonebins-api sidecar into CloneBins.app and wrap it in a DMG.
#
# Do not use `hdiutil create -srcfolder` alone: on macos-15-intel it often
# undersizes the temporary RW image, then copying clonebins-api fails with
# "No space left on device" on /Volumes/CloneBins even when the host has
# tens of GB free.
set -euo pipefail

SIDECAR="${1:?path to clonebins-api binary}"
APP="${2:?path to CloneBins.app}"
DMG_OUT="${3:?output .dmg path}"

if [[ ! -x "$SIDECAR" && ! -f "$SIDECAR" ]]; then
  echo "sidecar not found: $SIDECAR" >&2
  exit 1
fi
if [[ ! -d "$APP" ]]; then
  echo "app bundle not found: $APP" >&2
  exit 1
fi

cp "$SIDECAR" "$APP/Contents/MacOS/clonebins-api"
chmod +x "$APP/Contents/MacOS/clonebins-api"

# Ad-hoc sign so the nested sidecar is not a separate unsigned blob.
if command -v codesign >/dev/null; then
  codesign --force --deep --sign - "$APP"
fi

# Keep scratch on the output volume (not a tiny /tmp ramdisk).
OUT_DIR="$(cd "$(dirname "$DMG_OUT")" && pwd)"
WORK="${OUT_DIR}/.dmg-work-$$"
rm -rf "$WORK"
mkdir -p "$WORK"
export TMPDIR="$WORK"
trap 'rm -rf "$WORK"' EXIT

STAGING="$WORK/staging"
mkdir -p "$STAGING"
# Move (not copy) the .app so we do not need 2× disk for the sidecar.
mv "$APP" "$STAGING/CloneBins.app"
ln -s /Applications "$STAGING/Applications"
cat > "$STAGING/README-UNSIGNED.txt" <<'EOF'
CloneBins macOS build — unsigned / ad-hoc signed

This DMG is installable but not Developer ID signed or notarized.
Gatekeeper will warn on first launch.

Install:
  1. Drag CloneBins.app to Applications
  2. Right-click CloneBins.app → Open (or System Settings → Privacy & Security)

To publish notarized builds, add the Apple secrets listed in
apps/desktop/README.md and re-run "Release macOS DMG".
EOF

SRC_MB="$(du -sm "$STAGING" | awk '{print $1}')"
# 50% + 256MB headroom. hdiutil's own estimate is what overflowed on Intel.
SIZE_MB=$((SRC_MB + SRC_MB / 2 + 256))
if (( SIZE_MB < 512 )); then
  SIZE_MB=512
fi
echo "staging ${SRC_MB}M; creating ${SIZE_MB}M RW image"
du -sh "$STAGING/CloneBins.app" "$STAGING/CloneBins.app/Contents/MacOS/clonebins-api" || true
df -h "$WORK" "$OUT_DIR" . || true

RW="$WORK/CloneBins.rw.dmg"
rm -f "$RW" "$DMG_OUT"
hdiutil create \
  -size "${SIZE_MB}m" \
  -fs HFS+ \
  -volname CloneBins \
  -ov \
  "$RW"

ATTACH="$(hdiutil attach -readwrite -noverify -noautoopen "$RW")"
echo "$ATTACH"
DEVICE="$(echo "$ATTACH" | awk 'NR==1 {print $1}')"
MOUNT="$(echo "$ATTACH" | awk '/\/Volumes\// {print $NF; exit}')"
if [[ -z "${DEVICE:-}" || -z "${MOUNT:-}" || ! -d "$MOUNT" ]]; then
  echo "failed to attach $RW" >&2
  exit 1
fi

detach() {
  hdiutil detach "$DEVICE" -quiet 2>/dev/null || hdiutil detach "$MOUNT" -quiet 2>/dev/null || true
}
trap 'detach; rm -rf "$WORK"' EXIT

ditto "$STAGING/CloneBins.app" "$MOUNT/CloneBins.app"
ln -s /Applications "$MOUNT/Applications"
cp "$STAGING/README-UNSIGNED.txt" "$MOUNT/README-UNSIGNED.txt"
sync
detach
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$(dirname "$DMG_OUT")"
hdiutil convert "$RW" -format UDZO -imagekey zlib-level=9 -o "$DMG_OUT"
rm -f "$RW"
ls -lh "$DMG_OUT"
echo "Wrote $DMG_OUT"
