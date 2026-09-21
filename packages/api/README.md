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

v0.1.3 extras: `POST /api/models/download` always starts (Verify is not
required) and writes all seven YuNet + SFace ONNX files, falling back to
`/usr/bin/curl` if urllib/SSL fails. `POST /api/models/open-folder` and
`GET /api/models/install-command` support the UI fallbacks. Share passwords
are not logged.
