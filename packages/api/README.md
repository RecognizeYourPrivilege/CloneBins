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

v0.1.1 extras: `POST /api/jobs/from-share` and `POST /api/shares/probe` (SMB,
SFTP, FTP → local cache). `GET /api/models/status` and `POST /api/models/download`
for Verify / Download missing. Share passwords are not logged.
