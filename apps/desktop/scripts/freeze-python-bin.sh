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
      --collect-all clonebins_api
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
file "$OUT" || true
ls -lh "$OUT"
echo "Wrote $OUT"
