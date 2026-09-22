#!/usr/bin/env bash
# Download the seven YuNet + SFace ONNX weights into the desktop resource dir.
# Release workflows run this before packaging so the weights are baked into
# the app. They are not committed (see .gitignore *.onnx).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
DEST="${1:-$ROOT/apps/desktop/resources/models}"
PYTHON="${PYTHON:-python3}"

mkdir -p "$DEST"
echo "Fetching 7 ONNX models into $DEST"
"$PYTHON" -m clonebins_core.models --all --dir "$DEST"
"$PYTHON" - "$DEST" <<'PY'
import sys
from pathlib import Path

from clonebins_core.models import catalog_status

root = Path(sys.argv[1])
catalog = catalog_status(root)
if not catalog["all_ready"]:
    missing = [
        item["filename"]
        for family in ("yunet", "sface")
        for item in catalog[family]
        if not item["ready"]
    ]
    raise SystemExit("baked model set incomplete: " + ", ".join(missing))
print(f"baked {catalog['expected']} ONNX files in {root}")
PY
