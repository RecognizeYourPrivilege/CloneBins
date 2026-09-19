# CloneBins desktop (Tauri 2)

Native macOS + Linux window around the existing Vite/React UI. Clustering still
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

## Dev (Linux or macOS)

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
| `CloneBins-0.1.0-ubuntu-amd64.deb` | Ubuntu / Debian (`sudo apt install ./…deb`) |
| `CloneBins-0.1.0-linux-x64.AppImage` | Generic glibc (`chmod +x` then run) |
| `CloneBins-0.1.0-archlinux-x86_64.pkg.tar.zst` | Arch (`sudo pacman -U`) |
| `CloneBins-0.1.0-alpine-x86_64.apk` | Alpine (`apk add --allow-untrusted`) |

Ubuntu and Arch packages are the Tauri window plus a frozen `clonebins-api`
sidecar in `/usr/bin`. Alpine is musl: the workflow tries a WebKit GUI and
falls back to frozen `clonebins` + `clonebins-api` if that does not link.

To wrap binaries yourself (after a `tauri build --no-bundle` and a PyInstaller
sidecar in `dist/clonebins-api`):

```bash
apps/desktop/scripts/package-linux.sh deb \
  --desktop apps/desktop/src-tauri/target/release/clonebins-desktop \
  --api dist/clonebins-api \
  --out dist/release/CloneBins-0.1.0-ubuntu-amd64.deb
```

`arch` and `alpine` modes write `.pkg.tar.zst` / `.apk`. See
`.github/workflows/release-linux.yml`.

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

Apple notarization / Developer ID signing is **not** configured. For a local
unsigned build: `codesign --force --deep --sign - CloneBins.app`, or right-click
→ Open. Minimum macOS: 12.

## Privacy

The sidecar binds **loopback only**. Images never leave the machine. Face
weights, if used, are the same `~/.cache/clonebins/models` files as the CLI.
