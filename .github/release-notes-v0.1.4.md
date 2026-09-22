# CloneBins v0.1.4

Local-first identity bins for LoRA datasets. Processing stays on the machine that runs `clonebins-api` / `clonebins`. No cloud account.

## What’s new

- **Models ship with the app.** All seven YuNet + SFace ONNX files are baked into the desktop installers (and the Docker image). A fresh install already has them.
- **No Face models screen.** The app does not ask you to Verify or Download weights. On first launch it copies baked files into `~/.cache/clonebins/models` when they are missing. Settings still choose the YuNet and SFace variant.
- **macOS Intel DMG** is built on native `macos-15-intel` (not Rosetta), with an isolated venv, explicit PyInstaller `--target-arch`, and a larger DMG so the Intel job does not hang on a full disk image.

## Where weights live

| Place | Path |
| --- | --- |
| User cache (runtime) | `~/.cache/clonebins/models` or `CLONEBINS_MODELS_DIR` |
| macOS app | `CloneBins.app/Contents/Resources/models/` |
| Linux packages | `/usr/share/clonebins/models/` |
| Windows | `models/` next to `CloneBins.exe` |

There is no models UI. Power users: `clonebins models verify` (copy baked files, then download only gaps) or `clonebins models download --force`.

## Installers

| File | Platform |
| --- | --- |
| `CloneBins-0.1.4-macos-arm64.dmg` | Apple Silicon (unsigned / ad-hoc signed) |
| `CloneBins-0.1.4-macos-x64.dmg` | Intel Mac (unsigned / ad-hoc signed) |
| `CloneBins-0.1.4-ubuntu-amd64.deb` | Ubuntu / Debian |
| `CloneBins-0.1.4-linux-x64.AppImage` | Generic glibc Linux |
| `CloneBins-0.1.4-archlinux-x86_64.pkg.tar.zst` | Arch |
| `CloneBins-0.1.4-windows-x64-setup.exe` | Windows 10/11 NSIS |
| `CloneBins-0.1.4-windows-x64.zip` | Windows portable |

macOS DMGs are **unsigned / ad-hoc signed** (not Developer ID, not notarized). First launch: right-click CloneBins.app → Open. Each DMG includes `README-UNSIGNED.txt`.

See [CHANGELOG.md](https://github.com/RecognizeYourPrivilege/CloneBins/blob/main/CHANGELOG.md).
