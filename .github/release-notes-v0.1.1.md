# CloneBins v0.1.1

Local-first identity bins for LoRA datasets. Processing stays on the machine that runs `clonebins-api` / `clonebins`. No cloud account.

## What’s new

- **Network share mounts (SMB, SFTP, FTP).** In the web/desktop UI, connect to a share; images are cached locally and clustered with the existing pipeline. Credentials never appear in logs and are cleared after use.
- **face+body mode** no longer crashes with `all input arrays must have the same shape` when some images have a face and others do not.
- **Face models:** **Verify** / **Download missing** in the UI (with a live log). Download fetches only missing ONNX files. `clonebins models status`, `verify`, and `download` do the same on the CLI.
- **UI refresh** for the local web app (desktop reuses it).

## Installers

Desktop binaries are attached when GitHub Actions finishes building this tag. If they are not on this release yet, build from source (macOS/iOS still require a Mac):

```bash
python3 -m pip install -e packages/core -e packages/cli -e packages/api
cd apps/desktop && npm install && npm run build:unsigned
```

Expected asset names:

| File | Platform |
| --- | --- |
| `CloneBins-0.1.1-macos-arm64.dmg` | Apple Silicon (build from source / Actions) |
| `CloneBins-0.1.1-macos-x64.dmg` | Intel Mac |
| `CloneBins-0.1.1-ubuntu-amd64.deb` | Ubuntu / Debian |
| `CloneBins-0.1.1-linux-x64.AppImage` | Generic glibc Linux |
| `CloneBins-0.1.1-archlinux-x86_64.pkg.tar.zst` | Arch |
| `CloneBins-0.1.1-windows-x64-setup.exe` | Windows 10/11 NSIS |
| `CloneBins-0.1.1-windows-x64.zip` | Windows portable |

iOS remains build-from-source (`apps/ios`, XcodeGen).

See [CHANGELOG.md](https://github.com/RecognizeYourPrivilege/CloneBins/blob/main/CHANGELOG.md) and the README **Network shares** section.
