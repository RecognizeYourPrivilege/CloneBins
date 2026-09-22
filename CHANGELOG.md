# Changelog

## 0.1.4 — 2026-09-22

- **Baked models.** Desktop installers ship all seven YuNet + SFace ONNX files inside the app (macOS `Contents/Resources/models`, Linux `/usr/share/clonebins/models`, Windows `models/` next to the exe). Docker keeps a bundle copy at `/opt/clonebins/models` and seeds `/models`. Weights are downloaded in CI at package time, not committed to git.
- **No Face models UI.** Verify, Download, Open models folder, Copy install command, and the models log are gone. On app start (and before clustering) missing weights are copied from the baked bundle into `~/.cache/clonebins/models` with no prompt. CLI `clonebins models status|verify|download` remains for power users.
- **macOS Intel.** Native `macos-15-intel` runner, isolated venv, PyInstaller `--target-arch`, larger DMG headroom, and a bounded `hdiutil` so a stuck disk image fails instead of hanging the job. A release is published only when both DMGs succeed. Same-ref rebuilds cancel the previous run.
- Installers republished on the `v0.1.4` release: macOS arm64 + x64 DMGs, Ubuntu deb, AppImage, Arch package, Windows NSIS + zip.

## 0.1.3 — 2026-09-21

- **Download is always enabled.** The desktop/web **Download** button no longer waits for Verify. v0.1.2 still gated the button on `modelMissing > 0`, so a broken Verify left Download disabled and files never arrived.
- **Writes all 7 ONNX files** into `~/.cache/clonebins/models` (or `CLONEBINS_MODELS_DIR`). Hugging Face first, then GitHub LFS / raw / jsDelivr. If frozen-sidecar urllib/SSL fails, the downloader uses `/usr/bin/curl` (macOS always has it).
- **CLI fallback that always does the same thing:** `clonebins models download --force` (all seven files; `--force` re-fetches even if they look valid). UI also has **Open models folder** and **Copy install command**.
- Verify is best-effort status only. The sidecar still pins `HOME` / `CLONEBINS_MODELS_DIR` to the Mac user's real home (`/Users/$USER` if Finder left HOME empty).
- macOS arm64 + x64 DMGs rebuilt and published on the `v0.1.3` release.

## 0.1.2 — 2026-09-21

- **macOS Verify / Download:** the desktop sidecar and API now resolve the model cache as `Path.home() / ".cache" / "clonebins" / "models"` (or `CLONEBINS_MODELS_DIR`). Empty or literal `~` HOME values from Finder-launched apps no longer leave an unexpanded path. The Tauri sidecar exports the same `HOME` / `CLONEBINS_MODELS_DIR` as the Mac user running CloneBins.app.
- **7-file catalog:** Verify checks all four YuNet ONNX files (`2023mar`, `2023mar_int8`, `2023mar_int8bq`, `2026may`) and all three SFace files. Download fetches only missing files from Hugging Face (`opencv/face_detection_yunet`, `opencv/face_recognition_sface`), with opencv_zoo GitHub LFS as fallback (`2026may` is not on HF yet).
- macOS arm64 + x64 DMGs rebuilt on `macos-latest` / `macos-15-intel` and published on the `v0.1.2` release.

## 0.1.1 — 2026-09-20

- **Network shares:** connect to SMB, SFTP, or FTP from the web/desktop UI. Images are copied into a local cache and clustered with the existing `from-path` pipeline. Credentials stay on the API host, are never logged, and are cleared after the transfer.
- **face+body crash:** mixed folders (some images with a face, some appearance-only) no longer raise `ValueError: all input arrays must have the same shape`. Face and body parts are aligned to a single vector size before clustering.
- **Face models UI:** the unused “Download face models if missing” checkbox is gone. **Verify** lists present vs missing ONNX files in a log box; **Download missing** is disabled until Verify finds gaps, then fetches only those files. CLI `clonebins models status|verify|download` matches this (existing files are skipped).
- **UI:** refreshed dark theme for `apps/web` (and the desktop shell that reuses it) — typography, spacing, contrast, gradient accents. Upload, path, shares, settings, bins, rename/merge/zip are unchanged in behavior.
- Version bump to 0.1.1 across core, CLI, API, web, desktop, and iOS.
- **macOS Intel DMG:** the v0.1.1 tag job was cancelled (shared concurrency) and the follow-up Intel freeze failed on `macos-latest` because PyInstaller collected an arm64 `cryptography` wheel (paramiko/smbprotocol). Intel now builds on `macos-15-intel` with an isolated venv. DMG wrap uses an explicitly sized RW image (`hdiutil -srcfolder` overflowed on Intel); both unsigned DMGs attach to the same `v0.1.1` release.

## 0.1.0

Initial public release: CLI, local web UI, Tauri desktop, iOS LAN client, Docker image with YuNet/SFace weights.
