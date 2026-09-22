#!/usr/bin/env bash
# Collect a portable Windows zip (CloneBins.exe + clonebins-api.exe) or rename
# an NSIS installer. Works on Git Bash (CI) and Linux (packaging tests).
# Usage:
#   package-windows.sh zip --desktop EXE --api EXE [--extra FILE ...] --out FILE
#   package-windows.sh nsis --installer EXE --out FILE
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

MODE="${1:?mode required}"
shift

DESKTOP_EXE=""
API_EXE=""
INSTALLER=""
OUT=""
MODELS_DIR=""
EXTRAS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --desktop) DESKTOP_EXE="${2:?}"; shift 2 ;;
    --api) API_EXE="${2:?}"; shift 2 ;;
    --installer) INSTALLER="${2:?}"; shift 2 ;;
    --extra) EXTRAS+=("${2:?}"); shift 2 ;;
    --models) MODELS_DIR="${2:?}"; shift 2 ;;
    --out) OUT="${2:?}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

abspath() {
  local path="$1"
  if [[ "$path" = /* ]] || [[ "$path" =~ ^[A-Za-z]:[\\/] ]]; then
    printf '%s\n' "$path"
  else
    printf '%s\n' "$(pwd)/$path"
  fi
}

need_file() {
  local path="$1" label="$2"
  if [[ ! -f "$path" ]]; then
    echo "$label not found: $path" >&2
    exit 1
  fi
}

if [[ -z "$OUT" ]]; then
  echo "--out required" >&2
  exit 1
fi
mkdir -p "$(dirname "$OUT")"
OUT="$(abspath "$OUT")"

write_zip() {
  [[ -n "$DESKTOP_EXE" ]] || { echo "--desktop required for zip" >&2; exit 1; }
  [[ -n "$API_EXE" ]] || { echo "--api required for zip" >&2; exit 1; }
  DESKTOP_EXE="$(abspath "$DESKTOP_EXE")"
  API_EXE="$(abspath "$API_EXE")"
  need_file "$DESKTOP_EXE" "desktop exe"
  need_file "$API_EXE" "api sidecar"
  local extra_args=()
  local extra
  for extra in "${EXTRAS[@]+"${EXTRAS[@]}"}"; do
    extra="$(abspath "$extra")"
    need_file "$extra" "extra file"
    extra_args+=("$extra")
  done
  local models=""
  if [[ -n "$MODELS_DIR" ]]; then
    models="$(abspath "$MODELS_DIR")"
  else
    models="$ROOT/apps/desktop/resources/models"
  fi
  PYTHON_BIN="${PYTHON:-}"
  if [[ -z "$PYTHON_BIN" ]]; then
    if command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN=python3
    else
      PYTHON_BIN=python
    fi
  fi
  "$PYTHON_BIN" - "$OUT" "$DESKTOP_EXE" "$API_EXE" "$models" "${extra_args[@]}" <<'PY'
import sys
import zipfile
from pathlib import Path

out = Path(sys.argv[1])
desktop = Path(sys.argv[2])
api = Path(sys.argv[3])
models = Path(sys.argv[4])
extras = [Path(p) for p in sys.argv[5:]]
out.parent.mkdir(parents=True, exist_ok=True)
onnx = sorted(models.glob("*.onnx")) if models.is_dir() else []
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    zf.write(desktop, "CloneBins/CloneBins.exe")
    zf.write(api, "CloneBins/clonebins-api.exe")
    for extra in extras:
        zf.write(extra, f"CloneBins/{extra.name}")
    for weight in onnx:
        zf.write(weight, f"CloneBins/models/{weight.name}")
print(f"Wrote {out}")
print(f"  CloneBins/CloneBins.exe <- {desktop}")
print(f"  CloneBins/clonebins-api.exe <- {api}")
for extra in extras:
    print(f"  CloneBins/{extra.name} <- {extra}")
for weight in onnx:
    print(f"  CloneBins/models/{weight.name} <- {weight}")
PY
  ls -lh "$OUT"
}

copy_nsis() {
  [[ -n "$INSTALLER" ]] || { echo "--installer required for nsis" >&2; exit 1; }
  INSTALLER="$(abspath "$INSTALLER")"
  need_file "$INSTALLER" "NSIS installer"
  cp "$INSTALLER" "$OUT"
  ls -lh "$OUT"
  echo "Wrote $OUT"
}

case "$MODE" in
  zip) write_zip ;;
  nsis) copy_nsis ;;
  *) echo "unknown mode: $MODE (expected zip or nsis)" >&2; exit 1 ;;
esac
