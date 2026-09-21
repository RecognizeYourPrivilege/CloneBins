# CloneBins v0.1.3

Local-first identity bins for LoRA datasets. Processing stays on the machine that runs `clonebins-api` / `clonebins`. No cloud account.

## What’s new

- **Download always works.** The **Download** button is enabled without running Verify. It writes all seven YuNet + SFace ONNX files into `~/.cache/clonebins/models`. Progress streams into the log box.
- **Reliable fetch.** Hugging Face (`opencv/face_detection_yunet`, `opencv/face_recognition_sface`) plus GitHub LFS / raw / jsDelivr fallbacks. If the frozen PyInstaller sidecar cannot complete TLS, it shells out to `/usr/bin/curl`.
- **Terminal fallback:** `clonebins models download --force`
- **Open models folder** / **Copy install command** in the UI. Verify remains optional status.

## Installers

| File | Platform |
| --- | --- |
| `CloneBins-0.1.3-macos-arm64.dmg` | Apple Silicon (unsigned / ad-hoc signed) |
| `CloneBins-0.1.3-macos-x64.dmg` | Intel Mac (unsigned / ad-hoc signed) |
| `CloneBins-0.1.3-ubuntu-amd64.deb` | Ubuntu / Debian |
| `CloneBins-0.1.3-linux-x64.AppImage` | Generic glibc Linux |
| `CloneBins-0.1.3-archlinux-x86_64.pkg.tar.zst` | Arch |
| `CloneBins-0.1.3-windows-x64-setup.exe` | Windows 10/11 NSIS |
| `CloneBins-0.1.3-windows-x64.zip` | Windows portable |

macOS DMGs are **unsigned / ad-hoc signed** (not Developer ID, not notarized). First launch: right-click CloneBins.app → Open. Each DMG includes `README-UNSIGNED.txt`.

See [CHANGELOG.md](https://github.com/RecognizeYourPrivilege/CloneBins/blob/main/CHANGELOG.md).
