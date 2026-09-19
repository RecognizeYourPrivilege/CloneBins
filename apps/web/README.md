# CloneBins web

Local-first UI: upload images (or point at a folder on this machine), cluster
identities with `clonebins_core`, rename/merge/split bins, download a zip.

The browser talks only to the FastAPI process on localhost. There is no cloud
account.

## Run

From the repo root:

```bash
python3 -m pip install -e packages/core -e packages/api
clonebins-api
```

In another terminal:

```bash
cd apps/web
npm install
npm run dev
```

Open http://127.0.0.1:5173 — Vite proxies `/api` to http://127.0.0.1:8765.
