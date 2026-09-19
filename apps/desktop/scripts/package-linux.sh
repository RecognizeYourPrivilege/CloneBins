#!/usr/bin/env bash
# Build Ubuntu .deb or Arch .pkg.tar.zst for CloneBins.
# Usage:
#   package-linux.sh deb|arch --desktop BIN --api BIN --out FILE
#   package-linux.sh inject-deb --deb FILE --api BIN --out FILE
#   package-linux.sh inject-appimage --appimage FILE --api BIN --out FILE
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VERSION="${CLONEBINS_VERSION:-0.1.0}"
ICON_DIR="$ROOT/apps/desktop/src-tauri/icons"
URL="https://github.com/RecognizeYourPrivilege/CloneBins"
PKGDESC="Local-first clustering of AI-generated images into LoRA identity bins."

MODE="${1:?mode required}"
shift

DESKTOP_BIN=""
API_BIN=""
CLI_BIN=""
DEB_IN=""
APPIMAGE_IN=""
OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --desktop) DESKTOP_BIN="${2:?}"; shift 2 ;;
    --api) API_BIN="${2:?}"; shift 2 ;;
    --cli) CLI_BIN="${2:?}"; shift 2 ;;
    --deb) DEB_IN="${2:?}"; shift 2 ;;
    --appimage) APPIMAGE_IN="${2:?}"; shift 2 ;;
    --out) OUT="${2:?}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

abspath() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s\n' "$(pwd)/$path"
  fi
}

if [[ -n "$OUT" ]]; then
  mkdir -p "$(dirname "$OUT")"
  OUT="$(abspath "$OUT")"
fi
if [[ -n "$DESKTOP_BIN" ]]; then DESKTOP_BIN="$(abspath "$DESKTOP_BIN")"; fi
if [[ -n "$API_BIN" ]]; then API_BIN="$(abspath "$API_BIN")"; fi
if [[ -n "$CLI_BIN" ]]; then CLI_BIN="$(abspath "$CLI_BIN")"; fi
if [[ -n "$DEB_IN" ]]; then DEB_IN="$(abspath "$DEB_IN")"; fi
if [[ -n "$APPIMAGE_IN" ]]; then APPIMAGE_IN="$(abspath "$APPIMAGE_IN")"; fi

need_file() {
  local path="$1" label="$2"
  if [[ ! -f "$path" ]]; then
    echo "$label not found: $path" >&2
    exit 1
  fi
}

write_desktop_entry() {
  local dest="$1"
  mkdir -p "$(dirname "$dest")"
  cat >"$dest" <<EOF
[Desktop Entry]
Type=Application
Name=CloneBins
Comment=${PKGDESC}
Exec=clonebins-desktop
Icon=clonebins
Terminal=false
Categories=Graphics;Photography;
StartupNotify=true
EOF
}

install_icons() {
  local root="$1"
  local hicolor="$root/usr/share/icons/hicolor"
  install_one() {
    local size="$1" src="$2"
    if [[ -f "$src" ]]; then
      mkdir -p "$hicolor/${size}/apps"
      cp "$src" "$hicolor/${size}/apps/clonebins.png"
    fi
  }
  install_one 32x32 "$ICON_DIR/32x32.png"
  install_one 64x64 "$ICON_DIR/64x64.png"
  install_one 128x128 "$ICON_DIR/128x128.png"
  if [[ -f "$ICON_DIR/icon.png" ]]; then
    mkdir -p "$root/usr/share/pixmaps"
    cp "$ICON_DIR/icon.png" "$root/usr/share/pixmaps/clonebins.png"
  fi
}

install_bins() {
  local root="$1"
  mkdir -p "$root/usr/bin"
  if [[ -n "$DESKTOP_BIN" ]]; then
    need_file "$DESKTOP_BIN" "desktop binary"
    cp "$DESKTOP_BIN" "$root/usr/bin/clonebins-desktop"
    chmod 0755 "$root/usr/bin/clonebins-desktop"
  fi
  if [[ -n "$API_BIN" ]]; then
    need_file "$API_BIN" "api sidecar"
    cp "$API_BIN" "$root/usr/bin/clonebins-api"
    chmod 0755 "$root/usr/bin/clonebins-api"
  fi
  if [[ -n "$CLI_BIN" ]]; then
    need_file "$CLI_BIN" "cli binary"
    cp "$CLI_BIN" "$root/usr/bin/clonebins"
    chmod 0755 "$root/usr/bin/clonebins"
  fi
}

stage_payload() {
  local root="$1"
  rm -rf "$root"
  mkdir -p "$root"
  install_bins "$root"
  if [[ -n "$DESKTOP_BIN" ]]; then
    write_desktop_entry "$root/usr/share/applications/clonebins.desktop"
    install_icons "$root"
  fi
}

dir_size_bytes() {
  du -sb "$1" | awk '{print $1}'
}

finish_out() {
  mkdir -p "$(dirname "$OUT")"
  echo "Wrote $OUT"
  ls -lh "$OUT"
  file "$OUT" || true
}

package_deb() {
  [[ -n "$OUT" ]] || { echo "--out required" >&2; exit 1; }
  [[ -n "$DESKTOP_BIN" ]] || { echo "--desktop required for deb" >&2; exit 1; }
  [[ -n "$API_BIN" ]] || { echo "--api required for deb" >&2; exit 1; }
  local stage
  stage="$(mktemp -d)"
  trap 'rm -rf "$stage"' RETURN
  stage_payload "$stage/pkg"
  local size
  size="$(dir_size_bytes "$stage/pkg")"
  mkdir -p "$stage/pkg/DEBIAN"
  cat >"$stage/pkg/DEBIAN/control" <<EOF
Package: clonebins
Version: ${VERSION}
Section: graphics
Priority: optional
Architecture: amd64
Maintainer: CloneBins contributors <noreply@localhost>
Homepage: ${URL}
Installed-Size: $(( (size + 1023) / 1024 ))
Depends: libwebkit2gtk-4.1-0, libgtk-3-0, libglib2.0-0
Description: Cluster images by identity for LoRA datasets
 ${PKGDESC}
 Clustering stays on this machine; there is no cloud account.
EOF
  rm -f "$OUT"
  if command -v dpkg-deb >/dev/null; then
    dpkg-deb --build --root-owner-group "$stage/pkg" "$OUT"
  else
    echo "dpkg-deb not found" >&2
    exit 1
  fi
  finish_out
}

package_arch() {
  [[ -n "$OUT" ]] || { echo "--out required" >&2; exit 1; }
  [[ -n "$DESKTOP_BIN" ]] || { echo "--desktop required for arch" >&2; exit 1; }
  [[ -n "$API_BIN" ]] || { echo "--api required for arch" >&2; exit 1; }
  local stage
  stage="$(mktemp -d)"
  trap 'rm -rf "$stage"' RETURN
  stage_payload "$stage"
  local size builddate
  size="$(dir_size_bytes "$stage/usr")"
  builddate="$(date +%s)"
  cat >"$stage/.PKGINFO" <<EOF
pkgname = clonebins
pkgbase = clonebins
pkgver = ${VERSION}-1
pkgdesc = ${PKGDESC}
url = ${URL}
builddate = ${builddate}
packager = CloneBins CI
size = ${size}
arch = x86_64
license = MIT
depend = webkit2gtk-4.1
depend = gtk3
depend = glib2
EOF
  (
    cd "$stage"
    if command -v bsdtar >/dev/null; then
      bsdtar \
        --format=mtree \
        --options='!all,use-set,type,uid,gid,mode,time,size,sha256,link' \
        -czf .MTREE .PKGINFO usr
      if command -v zstd >/dev/null; then
        bsdtar -cf - .MTREE .PKGINFO usr | zstd -c -T0 --ultra -20 >"$OUT"
      else
        bsdtar -cJf "$OUT" .MTREE .PKGINFO usr
      fi
    else
      if command -v zstd >/dev/null; then
        tar --numeric-owner --owner=0 --group=0 -cf - .PKGINFO usr | zstd -c -T0 >"$OUT"
      else
        echo "need bsdtar+zstd or tar+zstd to write an Arch package" >&2
        exit 1
      fi
    fi
  )
  finish_out
}

inject_deb() {
  [[ -n "$OUT" ]] || { echo "--out required" >&2; exit 1; }
  [[ -n "$DEB_IN" ]] || { echo "--deb required" >&2; exit 1; }
  [[ -n "$API_BIN" ]] || { echo "--api required" >&2; exit 1; }
  need_file "$DEB_IN" "deb"
  need_file "$API_BIN" "api sidecar"
  command -v dpkg-deb >/dev/null || { echo "dpkg-deb required" >&2; exit 1; }
  local stage
  stage="$(mktemp -d)"
  trap 'rm -rf "$stage"' RETURN
  dpkg-deb -R "$DEB_IN" "$stage/pkg"
  mkdir -p "$stage/pkg/usr/bin"
  cp "$API_BIN" "$stage/pkg/usr/bin/clonebins-api"
  chmod 0755 "$stage/pkg/usr/bin/clonebins-api"
  rm -f "$OUT"
  dpkg-deb --build --root-owner-group "$stage/pkg" "$OUT"
  finish_out
}

inject_appimage() {
  [[ -n "$OUT" ]] || { echo "--out required" >&2; exit 1; }
  [[ -n "$APPIMAGE_IN" ]] || { echo "--appimage required" >&2; exit 1; }
  [[ -n "$API_BIN" ]] || { echo "--api required" >&2; exit 1; }
  need_file "$APPIMAGE_IN" "AppImage"
  need_file "$API_BIN" "api sidecar"
  local stage
  stage="$(mktemp -d)"
  trap 'rm -rf "$stage"' RETURN
  cp "$APPIMAGE_IN" "$stage/in.AppImage"
  chmod +x "$stage/in.AppImage"
  (
    cd "$stage"
    ./in.AppImage --appimage-extract
  )
  if [[ ! -d "$stage/squashfs-root" ]]; then
    echo "AppImage extract failed" >&2
    exit 1
  fi
  mkdir -p "$stage/squashfs-root/usr/bin"
  cp "$API_BIN" "$stage/squashfs-root/usr/bin/clonebins-api"
  chmod 0755 "$stage/squashfs-root/usr/bin/clonebins-api"
  local tool="${APPIMAGETOOL:-}"
  if [[ -z "$tool" ]]; then
    for c in appimagetool appimagetool-x86_64.AppImage; do
      if command -v "$c" >/dev/null; then
        tool="$(command -v "$c")"
        break
      fi
    done
  fi
  if [[ -z "$tool" || ! -x "$tool" ]]; then
    echo "appimagetool not found; set APPIMAGETOOL" >&2
    exit 1
  fi
  chmod +x "$tool" || true
  rm -f "$OUT"
  ARCH=x86_64 "$tool" "$stage/squashfs-root" "$OUT"
  chmod +x "$OUT"
  finish_out
}

case "$MODE" in
  deb) package_deb ;;
  arch) package_arch ;;
  inject-deb) inject_deb ;;
  inject-appimage) inject_appimage ;;
  *) echo "unknown mode: $MODE" >&2; exit 1 ;;
esac
