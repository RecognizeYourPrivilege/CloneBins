# CloneBins iOS (SwiftUI)

Thin SwiftUI client for the **same** `clonebins_core` pipeline. v1 does **not**
run face models on the phone. It uploads images you pick (Photos / Files) to a
**clonebins-api you run** (this Mac, or another machine on your LAN) and shows
the resulting `subject_XX` bins. Share the zip from a share sheet.

There is no cloud account. On-device Core ML (YuNet/SFace or Vision) is stubbed
as `CoreMLIdentityBackend` / `OnDeviceEmbeddingBackend` for a later swap;
clustering still goes through the Python API.

This folder was authored on Linux. **You need a Mac + Xcode to compile.** This
environment cannot sign or run an iOS Simulator.

## Limits (honest)

| Situation | What happens |
| --- | --- |
| iOS Simulator on the Mac that runs `clonebins-api` | Use `http://127.0.0.1:8765` — the simulator shares the Mac loopback. |
| Physical iPhone/iPad | Use `http://<Mac-LAN-IP>:8765`. Bind the API to the LAN (below). Phone and Mac on the same Wi-Fi. Allow local-network access when iOS prompts. |
| No reachable API | Import/cluster will fail; Ping in Settings shows “API unreachable”. |
| True offline / Core ML | **Not in v1.** `OnDeviceEmbeddingBackend` exists; implementation does not. |
| App Store / certificates | Out of scope. Leave `DEVELOPMENT_TEAM` empty and use your personal team in Xcode. |
| Linux CI / this cloud agent | Scaffold + docs only. No `xcodebuild`. |

## 1. Run the API on the Mac

```bash
cd /path/to/CloneBins
python3 -m pip install -e packages/core -e packages/api
clonebins-api
```

Simulator: that is enough (`127.0.0.1:8765`).

Physical device — listen on all interfaces (still your LAN, not the public internet):

```bash
CLONEBINS_API_HOST=0.0.0.0 CLONEBINS_API_PORT=8765 clonebins-api
```

Allow port 8765 in the Mac firewall if prompted. Find the Mac IP: System Settings →
Network, or `ipconfig getifaddr en0`.

ATS allows local HTTP (`NSAllowsLocalNetworking`). The app does **not** allow
arbitrary internet HTTP.

## 2. Generate the Xcode project

[XcodeGen](https://github.com/yonaskolb/XcodeGen) (`brew install xcodegen`):

```bash
cd apps/ios
xcodegen generate
open CloneBins.xcodeproj
```

Select a Simulator (or your device), set your **Team** under Signing if needed,
Run (⌘R).

Xcode 15+ / iOS 17+. No Swift packages required. `CloneBins.xcodeproj` is
generated and gitignored — always regenerate from `project.yml`.

## 3. Point the app at the API

In-app **Settings → API base URL** (persisted in UserDefaults):

- Simulator: `http://127.0.0.1:8765`
- Device: `http://192.168.x.x:8765` (your Mac)

Tap **Check connection**. If Ping fails, clustering cannot run.

## 4. Use it

1. Photos or Files → pick jpg/png/webp (HEIC from Photos is converted to JPEG
   on device; the API skips corrupt files).
2. Settings: threshold, min images, `face` / `face+body` (same meaning as CLI/web).
3. Preview bins with thumbnails, rename a subject, merge selected bins, toggle “in zip”.
4. **Zip** downloads `clonebins.zip` and opens the share sheet (Files, AirDrop, …).

## Layout

```
apps/ios/
  project.yml                 XcodeGen spec (source of truth for the Xcode project)
  README.md
  CloneBins/
    CloneBinsApp.swift
    Info.plist
    Assets.xcassets/
    Models/APIModels.swift
    Services/CloneBinsAPIClient.swift
    Services/EmbeddingBackend.swift   # Core ML stub
    Services/ImageImport.swift        # jpg/png/webp + HEIC→JPEG
    ViewModels/AppModel.swift
    Views/
```
