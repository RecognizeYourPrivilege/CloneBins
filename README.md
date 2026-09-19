# CloneBins

Cluster AI-generated images by **face** and **body/identity**, then drop each
identity into its own folder for LoRA training datasets.

v0.1 is a local CLI plus a shared Python core. Web, desktop, and iOS apps are
scaffolded as placeholders — they will wrap the same core later.

Processing is **offline-first**: images never leave the machine. Face model
weights are downloaded once (optional if you only need appearance clustering).

## Architecture (short)

One shared core, four clients:

| Piece | Status | Stack |
| --- | --- | --- |
| `packages/core` | **implemented** | Python: scan → embed → cluster → export |
| `packages/cli` | **implemented** | Typer + Rich |
| `apps/web` | placeholder | Vite/React + local FastAPI (later) |
| `apps/desktop` | placeholder | Tauri 2 + React + Python sidecar (later) |
| `apps/ios` | placeholder | SwiftUI / Core ML (later) |

**Why this stack:** Python is the lingua franca of LoRA tooling and ONNX face
models. Typer keeps the MVP usable on Linux and macOS today. OpenCV YuNet +
SFace give real face embeddings without PyTorch or InsightFace in the default
path (InsightFace is an optional swap). Body/appearance uses a light local
embedding so `--mode face+body` works without a CLIP download. Desktop/web can
reuse the core via FastAPI or a sidecar; iOS stays a thin client on the same
folder contract (`subject_01/`, `subject_02/`, …).

See [docs/architecture.md](docs/architecture.md) for the longer plan.

## Requirements

- Linux or macOS
- Python 3.10+
- `pip` or [`uv`](https://docs.astral.sh/uv/)
- OpenCV 4.x (pulled in automatically; the core package pins `opencv-python-headless>=4.8,<5`)

## Install

From the repo root (editable, recommended):

```bash
python3 -m pip install -e packages/core -e packages/cli
clonebins --help
```

With uv (workspace install of both packages + dev tools):

```bash
uv sync
uv run clonebins --help
```

## Face models (one-time, optional)

Default face clustering uses two local ONNX weights from the OpenCV zoo:

- YuNet face detector (`face_detection_yunet_2023mar.onnx`)
- SFace recognizer (`face_recognition_sface_2021dec.onnx`)

They are stored in `~/.cache/clonebins/models` (override with
`CLONEBINS_MODELS_DIR`). After they exist, **no network is used**.

```bash
clonebins models download
clonebins models status
```

`clonebins cluster` will also try to download them on first run unless you pass
`--no-download`.

`--mode face+body` still runs if models are missing: it falls back to a local
appearance embedding (color/layout) so you can dry-run the pipeline on any
folder. Face-only mode needs the ONNX files for real identity bins.

InsightFace (`buffalo_s` / `buffalo_l`) is **not** required. The core exposes
`clonebins_core.embed.insightface_backend.InsightFaceEmbedder` if you later
`pip install 'clonebins-core[insightface]'`.

## Run

```bash
clonebins cluster --input /path/to/images --output /path/to/bins
```

Useful options:

| Flag | Default | Meaning |
| --- | --- | --- |
| `--threshold` | `0.45` | Cosine **similarity** to merge images (higher = stricter) |
| `--min-images` | `2` | Ignore clusters smaller than this (not exported) |
| `--mode` | `face` | `face` or `face+body` |
| `--dry-run` | off | Print the plan; write nothing |
| `--copy` / `--hardlink` | `--copy` | How files land in output bins |
| `--keep-names` / `--rename-index` | `--keep-names` | Original names vs `00001.jpg` |
| `--subject-prefix` | `subject` | Folders `subject_01`, `subject_02`, … |
| `--no-download` | off | Never fetch face models |
| `--recursive` / `--no-recursive` | recursive | Scan subfolders |

Behavior:

1. Recursively scans `jpg` / `jpeg` / `png` / `webp`.
2. Skips unreadable files (logged, run continues).
3. Detects the largest face per image and embeds it; `face+body` also embeds
   whole-image appearance.
4. Clusters with average-linkage agglomerative clustering.
5. Prints a summary table (bin size + sample filenames).
6. Writes `output/subject_01/`, `output/subject_02/`, … (largest first).
7. Ctrl-C cancels cleanly (exit `130`).

If several faces appear in one image, only the **largest** is used (portrait /
character assumption). Images with no usable embedding are reported as
**unmatched** and not copied.

### Smoke check (no images required)

```bash
clonebins --help
clonebins cluster --help
```

### Tiny local demo

Any folder of PNG/JPEG works. If you do not have gens handy, the test suite
builds a few synthetic portraits:

```bash
python3 -m pytest tests/test_cli.py -q
```

Or cluster a folder yourself:

```bash
clonebins cluster \
  --input ./my_gens \
  --output ./lora_bins \
  --mode face+body \
  --threshold 0.45 \
  --min-images 4 \
  --dry-run
```

Remove `--dry-run` to write bins. Prefer `--mode face` once models are
downloaded.

## Example: prep a LoRA dataset

Goal: 10–30 images of **one** character, consistent identity, local files only.

1. Dump raw gens into `~/gens/char_x/` (png/jpg, any nested folders).
2. Install CloneBins and (recommended) download face models.
3. Cluster:

   ```bash
   clonebins cluster \
     --input ~/gens/char_x \
     --output ~/lora/char_x_bins \
     --mode face \
     --threshold 0.45 \
     --min-images 8 \
     --rename-index \
     --subject-prefix char
   ```

4. Inspect `~/lora/char_x_bins/char_01/` (largest bin — usually the main face).
   Spot-check other `char_XX` folders; they are other identities or looks that
   leaked into the dump.
5. Caption / crop as you normally would (kohya, OneTrainer, etc.). CloneBins
   only **sorts**; it does not train.
6. Point your trainer at `char_01/` (and optionally merge a second bin if it is
   the same person at a different camera distance).
7. If one person split across two bins, re-run with a **lower** `--threshold`
   (e.g. `0.35`). If two people merged, **raise** it (e.g. `0.55`).
8. `--mode face+body` helps when faces are stylized or small but outfits/hair
   colors are stable.

Hardlinks (`--hardlink`) save disk when source and destination are on the same
filesystem; CloneBins copies if linking fails.

## Privacy

- No cloud account, no upload, no telemetry.
- The only optional network call is fetching YuNet/SFace weights.
- Do not point `--input` at folders you would not want processed on that
  machine; output bins are extra copies/hardlinks of those files.

## Development

```bash
python3 -m pip install -e packages/core -e packages/cli pytest
python3 -m pytest
```

Layout:

```
packages/core/     shared pipeline (clonebins_core)
packages/cli/      Typer CLI (clonebins)
apps/web|desktop|ios/   placeholders
docs/architecture.md
tests/
```

## License

MIT
