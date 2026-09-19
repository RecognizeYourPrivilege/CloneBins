Desktop installers for macOS, Linux, and Windows. Clustering stays on your machine;
there is no cloud account. Each GUI package includes a bundled `clonebins-api`
sidecar (same `clonebins_core` pipeline as the CLI).

**Includes the face+body clustering fix** (no more `all input arrays must have the same shape` when YuNet misses a face).

### macOS

| File | Mac |
| --- | --- |
| `CloneBins-0.1.0-macos-arm64.dmg` | Apple Silicon (M1/M2/M3/M4) |
| `CloneBins-0.1.0-macos-x64.dmg` | Intel |

**Not notarized.** First launch: right-click the app → Open, or allow it under
System Settings → Privacy & Security. Ad-hoc signed on GitHub Actions.

### Linux

| File | Distro |
| --- | --- |
| `CloneBins-0.1.0-ubuntu-amd64.deb` | Ubuntu / Debian (glibc, WebKitGTK 4.1) |
| `CloneBins-0.1.0-linux-x64.AppImage` | Generic glibc Linux (`chmod +x`, then run) |
| `CloneBins-0.1.0-archlinux-x86_64.pkg.tar.zst` | Arch Linux |

Ubuntu:

```
sudo apt install ./CloneBins-0.1.0-ubuntu-amd64.deb
```

Arch:

```
sudo pacman -U CloneBins-0.1.0-archlinux-x86_64.pkg.tar.zst
```

### Windows

| File | Notes |
| --- | --- |
| `CloneBins-0.1.0-windows-x64-setup.exe` | NSIS installer (current user). Downloads WebView2 if missing. |
| `CloneBins-0.1.0-windows-x64.zip` | Portable: keep `CloneBins.exe` and `clonebins-api.exe` in the same folder |

Unsigned. SmartScreen may warn: More info → Run anyway. 64-bit Windows 10/11.
Keep `clonebins-api.exe` next to `CloneBins.exe` if you use the zip.
