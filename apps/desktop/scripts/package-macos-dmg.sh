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

# Baked YuNet + SFace weights. CI fills apps/desktop/resources/models;
# they are not committed (Git LFS / size). The sidecar copies these into
# ~/.cache/clonebins/models on Verify / first launch.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODELS_SRC="${CLONEBINS_BUNDLED_MODELS:-$SCRIPT_DIR/../resources/models}"
MODEL_DEST="$APP/Contents/Resources/models"
shopt -s nullglob
MODEL_FILES=("$MODELS_SRC"/*.onnx)
shopt -u nullglob
if [[ ${#MODEL_FILES[@]} -eq 0 ]]; then
  echo "warning: no baked ONNX models in $MODELS_SRC" >&2
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "release builds must run fetch-bundled-models.sh first" >&2
    exit 1
  fi
else
  mkdir -p "$MODEL_DEST"
  cp -f "${MODEL_FILES[@]}" "$MODEL_DEST/"
  echo "Baked ${#MODEL_FILES[@]} ONNX files into $MODEL_DEST"
  ls -lh "$MODEL_DEST"
fi

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
# 50% + 768MB headroom. hdiutil's own estimate overflowed on Intel (ENOSPC
# hang) before models were baked in; the extra slack covers the 7 ONNX files.
SIZE_MB=$((SRC_MB + SRC_MB / 2 + 768))
if (( SIZE_MB < 1536 )); then
  SIZE_MB=1536
fi
echo "staging ${SRC_MB}M; creating ${SIZE_MB}M RW image"
du -sh "$STAGING/CloneBins.app" "$STAGING/CloneBins.app/Contents/MacOS/clonebins-api" || true
df -h "$WORK" "$OUT_DIR" . || true
FREE_MB="$(df -m "$WORK" | awk 'NR==2 {print $4}')"
NEED_MB=$((SIZE_MB + 512))
if [[ -n "${FREE_MB:-}" && "$FREE_MB" -lt "$NEED_MB" ]]; then
  echo "Not enough free space for the DMG: ${FREE_MB}M free, need about ${NEED_MB}M" >&2
  exit 1
fi

# A stuck diskimages-helper from a cancelled Intel job will hang the next attach.
if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
  killall diskimages-helper 2>/dev/null || true
fi

run_bounded() {
  local secs="$1"
  shift
  "$@" &
  local pid=$!
  local waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if (( waited >= secs )); then
      echo "timed out after ${secs}s: $*" >&2
      kill -TERM "$pid" 2>/dev/null || true
      sleep 2
      kill -KILL "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      return 124
    fi
    sleep 5
    waited=$((waited + 5))
  done
  wait "$pid"
}

RW="$WORK/CloneBins.rw.dmg"
rm -f "$RW" "$DMG_OUT"
run_bounded 600 hdiutil create \
  -size "${SIZE_MB}m" \
  -fs HFS+ \
  -volname CloneBins \
  -ov \
  "$RW"

run_bounded 180 hdiutil attach -readwrite -nobrowse -noverify -noautoopen "$RW" >"$WORK/attach.txt"
ATTACH="$(cat "$WORK/attach.txt")"
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
run_bounded 600 hdiutil convert "$RW" -format UDZO -imagekey zlib-level=9 -o "$DMG_OUT"
rm -f "$RW"
ls -lh "$DMG_OUT"
echo "Wrote $DMG_OUT"
