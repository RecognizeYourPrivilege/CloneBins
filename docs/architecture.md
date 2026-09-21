# CloneBins architecture

CloneBins is a **shared-core monorepo**: one Python clustering pipeline, thin
clients. Core, CLI, local web UI, Tauri 2 desktop, and an iOS SwiftUI client
are implemented. iOS v1 talks to a user-run `clonebins-api` over loopback/LAN
and keeps the same `subject_XX` folder contract. On-device Core ML is stubbed.

## Why a shared core

Face detection, embedding, clustering, and export are the product. They should
not be reimplemented per platform. `packages/core` (`clonebins_core`) owns:

1. Recursive image scan (`jpg` / `jpeg` / `png` / `webp`)
2. Corrupt-tolerant decode
3. Face detect + embed (default: OpenCV YuNet + SFace ONNX)
4. Optional body/appearance embed (lightweight ReID-style histogram; CLIP later)
5. Agglomerative clustering on cosine similarity
6. Export to `output/<subject_prefix>_NN/` via copy or hardlink (CLI) or zip (web/desktop/iOS)

`packages/cli` is a Typer wrapper: flags, progress, preview table, Ctrl-C.
`packages/api` is a FastAPI wrapper: upload or local path, progress, rename /
merge / split / exclude, zip download. Both call `run_pipeline()`.

The desktop app is a Tauri 2 window around `apps/web`. It spawns `clonebins-api`
as a loopback sidecar so clustering still happens in Python, not in Rust.
GitHub Actions publishes Ubuntu `.deb` / AppImage, Arch `.pkg.tar.zst`,
Windows NSIS/zip, and macOS DMGs with that sidecar next to the binary.

The iOS app is a native SwiftUI client of that same FastAPI process. Photos you
pick are uploaded to an API **you run** (Simulator → `127.0.0.1`; device → LAN
IP with `CLONEBINS_API_HOST=0.0.0.0`). It does not embed faces on-device in v1.

```
                    ┌─────────────────────┐
                    │   clonebins_core    │
                    │  scan → embed →     │
                    │  cluster → export   │
                    └─────────┬───────────┘
                 ┌────────────┼────────────┐
                 ▼            ▼            ▼
              CLI         FastAPI       (tests)
            (Typer)      (web API)
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         Vite/React       Tauri 2      SwiftUI iOS
         (apps/web)      sidecar      LAN / 127.0.0.1
```

## Stack choices

| Layer | Choice | Why |
| --- | --- | --- |
| Core / CLI | Python 3.10+, Typer, Rich | Fast to iterate on CV code; Typer gives a solid UX; matches LoRA tooling (kohya, sd-scripts). |
| Faces | OpenCV YuNet + SFace (ONNX) | Small, CPU-friendly, no PyTorch. InsightFace (`buffalo_*`) is wired as an optional swap (`embed/insightface_backend.py`) if you want that ecosystem later. |
| Body / appearance | Histogram + spatial color grid (default); CLIP optional extra | `--mode face+body` is wired now without a 100MB+ download. Replace `AppearanceEmbedder` with CLIP / OSNet without touching cluster/export. |
| Clustering | Average-linkage agglomerative clustering, cosine distance | `--threshold` maps cleanly to cosine similarity. HDBSCAN is a later option for unknown cluster counts with density noise. |
| Web | Vite + React + TypeScript UI, local FastAPI (`clonebins-api`) | FastAPI imports `clonebins_core` directly. The browser only talks to localhost. Zip download of bins. |
| Desktop | Tauri 2 wrapping `apps/web` + Python sidecar | Native window on macOS, Linux, and Windows; folder picker, zip save. Sidecar is `clonebins-api` (same core). No Electron, no duplicated clustering. |
| iOS (v1) | SwiftUI + XcodeGen (`apps/ios`) | Photos/Files import, settings, cluster preview, rename/merge, zip share sheet. Talks to user-run `clonebins-api`. `OnDeviceEmbeddingBackend` / `CoreMLIdentityBackend` are stubs for a later YuNet+SFace (or Vision) path. Linux cannot `xcodebuild`. |

## Offline-first / privacy

- Default path is **on-device / local disk only**.
- No accounts, telemetry, or hosted APIs in v1.
- The web UI is not a SaaS: it is a frontend for a process you run yourself.
- The desktop sidecar binds `127.0.0.1` only and is stopped when the window exits
  (unless you already had `clonebins-api` running).
- iOS v1 is not a cloud client: it only talks to the API URL you type (default
  `http://127.0.0.1:8765`). ATS is limited to local networking
  (`NSAllowsLocalNetworking`). Physical devices need the API bound to `0.0.0.0`
  on your LAN — still not the public internet.
- Runtime does not need the network **after** YuNet + SFace weights are on disk
  (`~/.cache/clonebins/models`, overridable with `CLONEBINS_MODELS_DIR`).
- First-time `clonebins models download` (or the first cluster run with model
  download enabled) fetches those two ONNX files. Appearance-only
  `face+body` works with no models at all.

## Clustering behavior

- One embedding per image. If several faces are found, the **largest** box is used
  (typical for character portraits).
- `face` mode: drop images with no face embedding into the unmatched set.
- `face+body`: concatenate face ⊕ appearance (face-weighted). No face → zero
  face half + appearance, so every row is the same length (mixed folders used
  to crash with ``all input arrays must have the same shape``). Stylized gens
  still bin by look. After embedding, `build_embedding_matrix` re-aligns parts
  so a late-discovered face dimension cannot emit mixed row lengths.
- Network shares (SMB / SFTP / FTP) are an API I/O step: list/copy images into
  the job cache, then `run_pipeline()` as usual. Credentials are not logged.
- Face-model **Verify** is `GET /api/models/status` (best-effort). **Download**
  is `POST /api/models/download` and is not gated on Verify (poll
  `GET /api/models/download/{id}`). CLI: `clonebins models download --force`.
  Open folder: `POST /api/models/open-folder`.
- Web zip export: bins start unchecked; include individually or via Include all.
- Detector/recognizer: YuNet 2023 FP32 / INT8 / INT8-BQ and SFace 2021 FP32 /
  INT8 / INT8-BQ plus YuNet `2026may` from opencv_zoo (Hugging Face mirrors). Docker bakes all seven.
- `min-images`: clusters smaller than the cutoff are reported and not exported
  by default (web: shown as “below min”, off in the zip until you include or merge).
- Folder names are filesystem-safe: `subject_01`, `subject_02`, … (prefix
  configurable; web and iOS can rename bins before zip). Largest clusters first.

## Repo layout

```
CloneBins/
  packages/core/     clonebins_core
  packages/cli/      clonebins  (Typer)
  packages/api/      clonebins-api (FastAPI)
  apps/web/          Vite + React UI
  apps/desktop/      Tauri 2 shell (reuses apps/web)
  apps/ios/          SwiftUI + XcodeGen (LAN client; Core ML stub)
  docs/              this note
```

Python packaging is a `uv` workspace at the repo root (`pyproject.toml`) with
editable members under `packages/`. `pip install -e packages/core -e packages/cli -e packages/api`
works without uv.
