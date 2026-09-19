#!/usr/bin/env bash
# Copy a clonebins-api sidecar into CloneBins.app and wrap it in a DMG.
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

STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT
cp -R "$APP" "$STAGING/CloneBins.app"
ln -s /Applications "$STAGING/Applications"

mkdir -p "$(dirname "$DMG_OUT")"
rm -f "$DMG_OUT"
hdiutil create \
  -volname CloneBins \
  -srcfolder "$STAGING" \
  -ov \
  -format UDZO \
  "$DMG_OUT"

echo "Wrote $DMG_OUT"
