# clonebins-api

Local FastAPI process that imports `clonebins_core` (same pipeline as the CLI)
and serves the Vite web UI.

```bash
pip install -e packages/core -e packages/api
clonebins-api
# http://127.0.0.1:8765/api/health
```

The browser, Tauri desktop webview, and iOS SwiftUI client talk only to this
process. There is no cloud account.

Bind `127.0.0.1` (default) for web/desktop/Simulator. For a physical iPhone on
the same Wi-Fi: `CLONEBINS_API_HOST=0.0.0.0 clonebins-api`.

v0.1.4 extras: `POST /api/models/verify` checks `~/.cache/clonebins/models`,
copies ONNX files baked into the app, then downloads only what is missing.
`POST /api/models/download` always starts (Verify is not required) and does
the same fill, falling back to `/usr/bin/curl` if urllib/SSL fails. Poll
`GET /api/models/download/{id}` for either task. `POST /api/models/open-folder`
and `GET /api/models/install-command` support the UI fallbacks. Share passwords
are not logged.
