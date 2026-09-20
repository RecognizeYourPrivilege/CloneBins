# Changelog

## 0.1.1 — 2026-09-20

- **Network shares:** connect to SMB, SFTP, or FTP from the web/desktop UI. Images are copied into a local cache and clustered with the existing `from-path` pipeline. Credentials stay on the API host, are never logged, and are cleared after the transfer.
- **face+body crash:** mixed folders (some images with a face, some appearance-only) no longer raise `ValueError: all input arrays must have the same shape`. Face and body parts are aligned to a single vector size before clustering.
- **Face models UI:** the unused “Download face models if missing” checkbox is gone. **Verify** lists present vs missing ONNX files in a log box; **Download missing** is disabled until Verify finds gaps, then fetches only those files. CLI `clonebins models status|verify|download` matches this (existing files are skipped).
- **UI:** refreshed dark theme for `apps/web` (and the desktop shell that reuses it) — typography, spacing, contrast, gradient accents. Upload, path, shares, settings, bins, rename/merge/zip are unchanged in behavior.
- Version bump to 0.1.1 across core, CLI, API, web, desktop, and iOS.
- **macOS Intel DMG:** the v0.1.1 tag job was cancelled (shared concurrency) and the follow-up Intel freeze failed on `macos-latest` because PyInstaller collected an arm64 `cryptography` wheel (paramiko/smbprotocol). Intel now builds on `macos-15-intel` with an isolated venv. DMG wrap uses an explicitly sized RW image (`hdiutil -srcfolder` overflowed on Intel); both unsigned DMGs attach to the same `v0.1.1` release.

## 0.1.0

Initial public release: CLI, local web UI, Tauri desktop, iOS LAN client, Docker image with YuNet/SFace weights.
