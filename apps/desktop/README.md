# CloneBins desktop (Tauri 2)

Native macOS, Linux, and Windows window around the existing Vite/React UI. Clustering still
runs in `clonebins_core` through the `clonebins-api` Python sidecar on
`127.0.0.1:8765`. There is no cloud account.

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Tauri window│────▶│ clonebins-api    │────▶│ clonebins_core  │
│ (apps/web)  │     │ FastAPI sidecar  │     │ scan/embed/zip  │
└─────────────┘     └──────────────────┘     └─────────────────┘
```

On launch the shell checks port 8765. If nothing is listening it spawns
`clonebins-api` (or `python3 -m clonebins_api`) and kills that child on quit.
If you already ran `clonebins-api` yourself, the window reuses it.

Native **Browse** (source folder) and **Save zip…** (output) use Tauri dialogs
when the UI detects the desktop runtime. The browser build still uses a path
field and a normal download.

## Prerequisites

- Python 3.10+ with:

  ```bash
  pip install -e packages/core -e packages/api
  ```

- Node 20+ and **Rust 1.85+** (Tauri 2), plus Tauri Linux packages on Debian/Ubuntu:

  ```bash
  sudo apt install libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev patchelf
  ```

  macOS: Xcode CLT (`xcode-select --install`). No extra GTK packages.
  Windows: [WebView2](https://developer.microsoft.com/microsoft-edge/webview2/)
  (Windows 11 includes it; the NSIS installer bootstraps it on Windows 10).

## Dev (Linux, macOS, or Windows)

From the repo root:

```bash
# terminal optional: API already running is fine
clonebins-api

cd apps/desktop
npm install
npm run dev
```

`tauri dev` starts Vite in `apps/web` (`http://127.0.0.1:5173`) and opens the
native window. The webview proxies `/api` to the sidecar in dev.

Override the interpreter with `CLONEBINS_PYTHON=/path/to/python` if `python3`
is not the env that has CloneBins installed.

## Build

### Linux (this repo’s CI / a typical VM)

```bash
cd apps/desktop
npm install
npm run build:unsigned
```

`build:unsigned` is `tauri build --no-bundle`: it compiles the binary without
deb/AppImage packaging (FUSE/AppImage is often missing on headless VMs).

The binary lands at:

`apps/desktop/src-tauri/target/release/clonebins-desktop`

GitHub Actions publishes installers on
[Releases](https://github.com/RecognizeYourPrivilege/CloneBins/releases):

| File | Distro |
| --- | --- |
| `CloneBins-0.1.4-ubuntu-amd64.deb` | Ubuntu / Debian (`sudo apt install ./…deb`) |
| `CloneBins-0.1.4-linux-x64.AppImage` | Generic glibc (`chmod +x` then run) |
| `CloneBins-0.1.4-archlinux-x86_64.pkg.tar.zst` | Arch (`sudo pacman -U`) |
| `CloneBins-0.1.4-windows-x64-setup.exe` | Windows 10/11 NSIS |
| `CloneBins-0.1.4-windows-x64.zip` | Windows portable zip |

Ubuntu and Arch packages are the Tauri window plus a frozen `clonebins-api`
sidecar in `/usr/bin`.

To wrap binaries yourself (after a `tauri build --no-bundle` and a PyInstaller
sidecar in `dist/clonebins-api`):

```bash
apps/desktop/scripts/package-linux.sh deb \
  --desktop apps/desktop/src-tauri/target/release/clonebins-desktop \
  --api dist/clonebins-api \
  --out dist/release/CloneBins-0.1.4-ubuntu-amd64.deb
```

`arch` mode writes `.pkg.tar.zst`. See `.github/workflows/release-linux.yml`.

Full installers locally (when desktop portal / FUSE work):

```bash
npm run build
# deb + AppImage under src-tauri/target/release/bundle/
```

### macOS

GitHub Actions (macOS runner) publishes **CloneBins.app inside a DMG** on
[Releases](https://github.com/RecognizeYourPrivilege/CloneBins/releases) for
**Apple Silicon** (`*-macos-arm64.dmg`) and **Intel** (`*-macos-x64.dmg`). That
job is not this Linux VM. The app is ad-hoc signed, not notarized.

To rebuild the same artifact on a Mac:

```bash
cd apps/desktop
npm install
npx tauri build --bundles app
# then scripts/package-macos-dmg.sh injects clonebins-api and wraps a DMG
```

Produces `src-tauri/target/release/bundle/dmg/` and
`src-tauri/target/release/bundle/macos/CloneBins.app`. CI then copies a frozen
`clonebins-api` sidecar into `Contents/MacOS/` and wraps a DMG (see
`scripts/package-macos-dmg.sh`).

Apple notarization / Developer ID signing is **not** configured. CI ad-hoc
signs (`codesign --force --deep --sign -`) so the DMG is installable: drag
to Applications, then right-click → Open. Each DMG also has
`README-UNSIGNED.txt`. Minimum macOS: 12.

Intel CI uses the `macos-15-intel` runner (native x86_64). Do not freeze the
sidecar under Rosetta on Apple Silicon: `paramiko` / `smbprotocol` pull
`cryptography`, and the runner Framework Python’s arm64 wheel makes
PyInstaller fail with `IncompatibleBinaryArchError`.

### Optional Apple signing secrets

Not required for the unsigned v0.1.4 DMGs. Add these GitHub Actions secrets
only if you want CI to Developer ID sign and notarize later:

| Secret | Purpose |
| --- | --- |
| `APPLE_CERTIFICATE` | Base64-encoded Developer ID Application `.p12` |
| `APPLE_CERTIFICATE_PASSWORD` | Password for that `.p12` |
| `APPLE_SIGNING_IDENTITY` | e.g. `Developer ID Application: Name (TEAMID)` |
| `APPLE_TEAM_ID` | 10-character Team ID |
| `APPLE_ID` | Apple ID email for `notarytool` |
| `APPLE_APP_PASSWORD` | App-specific password |
| `APPLE_API_KEY` | App Store Connect API key (`.p8` contents) |
| `APPLE_API_KEY_ID` | Key ID |
| `APPLE_API_ISSUER` | Issuer UUID |

Until those exist, “Release macOS DMG” keeps producing unsigned / ad-hoc
DMGs and attaches them to the tag (`workflow_dispatch` with `tag=v0.1.4`
rebuilds the same release).

### Windows

GitHub Actions (`windows-latest`) publishes an NSIS installer and a portable
zip on [Releases](https://github.com/RecognizeYourPrivilege/CloneBins/releases).
The zip is `CloneBins.exe` plus `clonebins-api.exe` in the same folder (the
window looks next to the exe for the sidecar). Unsigned: SmartScreen may show
More info → Run anyway.

```bash
cd apps/desktop
npm install
npx tauri build --bundles nsis --config src-tauri/windows-sidecar.tauri.conf.json
```

See `.github/workflows/release-windows.yml`.

## Privacy

The sidecar binds **loopback only**. Images never leave the machine. Face
weights live in `~/.cache/clonebins/models` (the same cache as the CLI).
Release builds bake the seven ONNX files into the app
(`Contents/Resources/models` on macOS, `/usr/share/clonebins/models` on Linux,
`models/` next to the exe on Windows). The sidecar sets `CLONEBINS_BUNDLED_MODELS`
so startup can copy those into the cache with no models UI. CI downloads the
weights with `scripts/fetch-bundled-models.sh`; they are not committed.
