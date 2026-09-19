# CloneBins architecture

CloneBins is a **shared-core monorepo**: one Python clustering pipeline, four thin
clients. v0.1 ships the core + CLI. Web, desktop, and iOS are stubs with the
same folder contract so UIs can land later without rewriting clustering.

## Why a shared core

Face detection, embedding, clustering, and export are the product. They should
not be reimplemented per platform. `packages/core` (`clonebins_core`) owns:

1. Recursive image scan (`jpg` / `jpeg` / `png` / `webp`)
2. Corrupt-tolerant decode
3. Face detect + embed (default: OpenCV YuNet + SFace ONNX)
4. Optional body/appearance embed (lightweight ReID-style histogram; CLIP later)
5. Agglomerative clustering on cosine similarity
6. Export to `output/<subject_prefix>_NN/` via copy or hardlink

`packages/cli` is a Typer wrapper: flags, progress, preview table, Ctrl-C.

Future clients call the same `run_pipeline()` (or a small local HTTP adapter).

```
                    ┌─────────────────────┐
                    │   clonebins_core    │
                    │  scan → embed →     │
                    │  cluster → export   │
                    └─────────┬───────────┘
            ┌─────────┬───────┼────────┬──────────┐
            ▼         ▼       ▼        ▼          ▼
         CLI       FastAPI   Tauri    SwiftUI   (tests)
       (Typer)    (web API) sidecar   (iOS)
                      │       │
                      └───────┴── Vite/React UI (later)
```

## Stack choices

| Layer | Choice | Why |
| --- | --- | --- |
| Core / CLI | Python 3.10+, Typer, Rich | Fast to iterate on CV code; Typer gives a solid UX; matches LoRA tooling (kohya, sd-scripts). |
| Faces | OpenCV YuNet + SFace (ONNX) | Small, CPU-friendly, no PyTorch. InsightFace (`buffalo_*`) is wired as an optional swap (`embed/insightface_backend.py`) if you want that ecosystem later. |
| Body / appearance | Histogram + spatial color grid (default); CLIP optional extra | `--mode face+body` is wired now without a 100MB+ download. Replace `AppearanceEmbedder` with CLIP / OSNet without touching cluster/export. |
| Clustering | Average-linkage agglomerative clustering, cosine distance | `--threshold` maps cleanly to cosine similarity. HDBSCAN is a later option for unknown cluster counts with density noise. |
| Web (later) | Vite + React + local FastAPI | FastAPI imports `clonebins_core` directly. UI never sends images to a cloud. Zip download of bins. |
| Desktop (later) | Tauri 2 + React + Python sidecar | Wraps the web UI; sidecar is the same core. Native folder pickers, no Electron. |
| iOS (later) | SwiftUI | Thin client. On-device: Core ML conversion of YuNet/SFace (or Apple Vision). Same `subject_XX` export contract. |

## Offline-first / privacy

- Default path is **on-device / local disk only**.
- No accounts, telemetry, or hosted APIs in v1.
- Runtime does not need the network **after** YuNet + SFace weights are on disk
  (`~/.cache/clonebins/models`, overridable with `CLONEBINS_MODELS_DIR`).
- First-time `clonebins models download` (or the first `cluster` run without
  `--no-download`) fetches those two ONNX files. Appearance-only
  `--mode face+body` works with no models at all.

## Clustering behavior

- One embedding per image. If several faces are found, the **largest** box is used
  (typical for character portraits).
- `--mode face`: drop images with no face embedding into the unmatched set.
- `--mode face+body`: concatenate face ⊕ appearance (face-weighted). No face →
  appearance only, so stylized gens still bin by look.
- `--min-images`: clusters smaller than the cutoff are reported and **not**
  exported (avoids 1-image LoRA junk folders).
- Folder names are filesystem-safe: `subject_01`, `subject_02`, … (prefix
  configurable). Largest clusters first.

## Repo layout

```
CloneBins/
  packages/core/     clonebins_core
  packages/cli/      clonebins  (Typer)
  apps/web/          placeholder
  apps/desktop/      placeholder
  apps/ios/          placeholder
  docs/              this note
```

Python packaging is a `uv` workspace at the repo root (`pyproject.toml`) with
editable members under `packages/`. `pip install -e packages/core -e packages/cli`
works without uv.
