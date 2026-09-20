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

**Verify** / **Download missing** manage the local YuNet/SFace cache (log box
under Face models). **Network share** copies SMB/SFTP/FTP images into a local
job cache, then clusters them like a folder path.

Bins are **not** in the zip until you tick **in zip** or **Include all in zip**.
**open ↗** on a thumbnail opens the original file in a new window.

## Docker

From the repo root (API + built UI + all seven opencv_zoo ONNX files):

```bash
docker compose up --build
```

Then http://127.0.0.1:8765 — no separate `clonebins-api` process.
