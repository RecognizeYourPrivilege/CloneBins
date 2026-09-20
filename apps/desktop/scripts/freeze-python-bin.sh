#!/usr/bin/env bash
# Freeze clonebins-api and/or clonebins with PyInstaller (Linux/macOS/Windows).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

KIND="${1:?usage: freeze-python-bin.sh api|cli [python]}"
PYTHON="${2:-${PYTHON:-python3}}"

case "$KIND" in
  api)
    NAME=clonebins-api
    ENTRY=packages/api/src/clonebins_api/__main__.py
    extra=(
      --hidden-import uvicorn.logging
      --hidden-import uvicorn.loops.auto
      --hidden-import uvicorn.protocols.http.auto
      --hidden-import uvicorn.protocols.websockets.auto
      --hidden-import uvicorn.lifespan.on
      --hidden-import clonebins_api.shares
      --hidden-import paramiko
      --hidden-import smbclient
      --hidden-import smbprotocol
      --hidden-import cryptography
      --collect-all clonebins_api
      --collect-all paramiko
      --collect-all smbprotocol
    )
    ;;
  cli)
    NAME=clonebins
    ENTRY=packages/cli/src/clonebins_cli/__main__.py
    extra=(
      --hidden-import typer
      --hidden-import rich
      --collect-all clonebins_cli
    )
    ;;
  *)
    echo "unknown kind: $KIND (expected api or cli)" >&2
    exit 1
    ;;
esac

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
mkdir -p "$ROOT/dist"

target_args=()
if [[ -n "${TARGET_ARCH:-}" ]]; then
  target_args+=(--target-arch "$TARGET_ARCH")
fi

"$PYTHON" -m PyInstaller \
  --noconfirm --clean --onefile \
  --name "$NAME" \
  --distpath "$ROOT/dist" \
  --workpath "$WORKDIR/build" \
  --specpath "$WORKDIR" \
  --hidden-import sklearn.cluster \
  --hidden-import sklearn.metrics.pairwise \
  --collect-all clonebins_core \
  --exclude-module tkinter \
  --exclude-module matplotlib \
  --exclude-module sklearn.datasets \
  --exclude-module sklearn.tests \
  --exclude-module scipy.tests \
  "${target_args[@]}" \
  "${extra[@]}" \
  "$ENTRY"

# PyInstaller writes dist/$NAME on Unix and dist/$NAME.exe on Windows.
if [[ -f "$ROOT/dist/${NAME}.exe" ]]; then
  OUT="$ROOT/dist/${NAME}.exe"
elif [[ -f "$ROOT/dist/$NAME" ]]; then
  OUT="$ROOT/dist/$NAME"
else
  echo "PyInstaller did not write dist/$NAME or dist/${NAME}.exe" >&2
  ls -la "$ROOT/dist" >&2 || true
  exit 1
fi
chmod +x "$OUT" 2>/dev/null || true
info="$(file "$OUT" 2>/dev/null || true)"
echo "$info"
ls -lh "$OUT"
if [[ -n "${TARGET_ARCH:-}" && -n "$info" ]]; then
  case "$TARGET_ARCH" in
    x86_64)
      echo "$info" | grep -Eq 'x86_64|i386' || {
        echo "expected $TARGET_ARCH binary: $info" >&2
        exit 1
      }
      ;;
    arm64)
      echo "$info" | grep -Eq 'arm64|aarch64' || {
        echo "expected $TARGET_ARCH binary: $info" >&2
        exit 1
      }
      ;;
  esac
fi
echo "Wrote $OUT"
