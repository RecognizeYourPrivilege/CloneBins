# clonebins-api

Local FastAPI process that imports `clonebins_core` (same pipeline as the CLI)
and serves the Vite web UI.

```bash
pip install -e packages/core -e packages/api
clonebins-api
# http://127.0.0.1:8765/api/health
```

The browser talks only to this process. There is no cloud account.
