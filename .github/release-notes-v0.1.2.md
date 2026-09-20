# CloneBins v0.1.2

Local-first identity bins for LoRA datasets. Processing stays on the machine that runs `clonebins-api` / `clonebins`. No cloud account.

## What’s new

- **macOS Verify / Download.** Models are resolved at `~/.cache/clonebins/models` (or `CLONEBINS_MODELS_DIR`). The desktop sidecar inherits the same `HOME` as the Mac user running CloneBins.app, so Verify sees the same cache as a shell `~`.
- **Seven ONNX files.** Verify reports present vs missing for all four YuNet files (`face_detection_yunet_2023mar.onnx`, `_int8.onnx`, `_int8bq.onnx`, `face_detection_yunet_2026may.onnx`) and all three SFace files. Download fetches only missing files from Hugging Face (`opencv/face_detection_yunet`, `opencv/face_recognition_sface`), with opencv_zoo GitHub LFS as fallback (`2026may` is published on GitHub, not yet on HF).

## Installers

| File | Platform |
| --- | --- |
| `CloneBins-0.1.2-macos-arm64.dmg` | Apple Silicon (unsigned / ad-hoc signed) |
| `CloneBins-0.1.2-macos-x64.dmg` | Intel Mac (unsigned / ad-hoc signed) |
| `CloneBins-0.1.2-ubuntu-amd64.deb` | Ubuntu / Debian |
| `CloneBins-0.1.2-linux-x64.AppImage` | Generic glibc Linux |
| `CloneBins-0.1.2-archlinux-x86_64.pkg.tar.zst` | Arch |
| `CloneBins-0.1.2-windows-x64-setup.exe` | Windows 10/11 NSIS |
| `CloneBins-0.1.2-windows-x64.zip` | Windows portable |

macOS DMGs are **unsigned / ad-hoc signed** (not Developer ID, not notarized). First launch: right-click CloneBins.app → Open. Each DMG includes `README-UNSIGNED.txt`.

See [CHANGELOG.md](https://github.com/RecognizeYourPrivilege/CloneBins/blob/main/CHANGELOG.md).
