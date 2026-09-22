"""FastAPI app: local-only clustering API for the Vite UI."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from clonebins_api import __version__
from clonebins_api.jobs import JobError, store
from clonebins_api.schemas import (
    ClusterSettings,
    ExcludeRequest,
    ExtractRequest,
    IncludeRequest,
    MergeRequest,
    PathRequest,
    RenameRequest,
    ShareRequest,
)
from clonebins_api.shares import ShareError, ShareSpec, probe_share
from clonebins_core.models import (
    INSTALL_COMMAND,
    catalog_status,
    copy_bundled_into_cache,
    curl_install_script,
    default_models_dir,
    missing_model_specs,
    models_present,
)

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """First launch: copy ONNX weights baked into the app into the user cache.

    This is silent. There is no models UI. Network download stays on the CLI
    (`clonebins models …`) so startup does not block on Hugging Face.
    """
    try:
        copied = copy_bundled_into_cache()
        if copied:
            print(
                f"Seeded {len(copied)} baked ONNX file(s) into {default_models_dir()}",
                flush=True,
            )
    except Exception as exc:
        print(f"Baked model seed skipped: {exc}", flush=True)
    yield


app = FastAPI(
    title="CloneBins API",
    version=__version__,
    description="Local clustering API. Images stay on this machine.",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Loopback-only server. Tauri webview origins vary (tauri://, http://tauri.localhost).
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _models_payload(models_dir: Path | None = None) -> dict:
    directory = models_dir or default_models_dir()
    catalog = catalog_status(directory)
    missing = missing_model_specs(directory)
    return {
        **catalog,
        "missing": missing,
        "missing_count": len(missing),
        "ready": models_present(directory),
        "catalog_ready": catalog["all_ready"],
        "install_command": INSTALL_COMMAND,
        "curl_script": curl_install_script(directory),
    }


@app.exception_handler(JobError)
def _job_error(_request, exc: JobError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)


@app.exception_handler(ShareError)
def _share_error(_request, exc: ShareError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.get("/api/health")
def health() -> dict:
    directory = default_models_dir()
    catalog = catalog_status(directory)
    return {
        "ok": True,
        "version": __version__,
        "privacy": "local",
        "models_dir": str(directory),
        "models_ready": models_present(directory),
        "models": catalog,
        "install_command": INSTALL_COMMAND,
    }


@app.get("/api/models")
def models() -> dict:
    return catalog_status()


@app.get("/api/models/status")
def models_status() -> dict:
    """Read-only catalog: which YuNet / SFace ONNX files are present vs missing."""
    return _models_payload()


@app.post("/api/jobs/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict:
    payload: list[tuple[str, bytes]] = []
    for item in files:
        data = await item.read()
        payload.append((item.filename or "upload.bin", data))
    job = store.create_upload(payload)
    return job.to_dict()


@app.post("/api/jobs/from-path")
def from_path(body: PathRequest) -> dict:
    job = store.create_from_path(body.path)
    return job.to_dict()


@app.post("/api/shares/probe")
def share_probe(body: ShareRequest) -> dict:
    spec = _share_spec(body)
    try:
        return probe_share(spec)
    finally:
        spec.clear_secrets()


@app.post("/api/jobs/from-share")
def from_share(body: ShareRequest) -> dict:
    spec = _share_spec(body)
    try:
        job = store.create_from_share(spec)
    finally:
        spec.clear_secrets()
    return job.to_dict()


def _share_spec(body: ShareRequest) -> ShareSpec:
    return ShareSpec(
        protocol=body.protocol,
        host=body.host,
        path=body.path,
        username=body.username,
        password=body.password,
        private_key=body.private_key,
        port=body.port,
    )


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    return store.get(job_id).to_dict()


@app.post("/api/jobs/{job_id}/cluster")
def cluster(job_id: str, settings: ClusterSettings) -> dict:
    job = store.start_cluster(job_id, settings)
    return job.to_dict()


@app.post("/api/jobs/{job_id}/cancel")
def cancel(job_id: str) -> dict:
    return store.cancel(job_id).to_dict()


@app.patch("/api/jobs/{job_id}/clusters/{cluster_id}")
def rename(job_id: str, cluster_id: str, body: RenameRequest) -> dict:
    return store.rename(job_id, cluster_id, body.name).to_dict()


@app.post("/api/jobs/{job_id}/clusters/{cluster_id}/include")
def include_cluster(job_id: str, cluster_id: str, body: IncludeRequest) -> dict:
    return store.set_included(job_id, cluster_id, body.included).to_dict()


@app.post("/api/jobs/{job_id}/include-all")
def include_all(job_id: str, body: IncludeRequest) -> dict:
    return store.set_included_all(job_id, body.included).to_dict()


@app.post("/api/jobs/{job_id}/merge")
def merge(job_id: str, body: MergeRequest) -> dict:
    return store.merge(job_id, body.cluster_ids).to_dict()


@app.post("/api/jobs/{job_id}/clusters/{cluster_id}/extract")
def extract(job_id: str, cluster_id: str, body: ExtractRequest) -> dict:
    return store.extract(job_id, cluster_id, body.image_ids).to_dict()


@app.post("/api/jobs/{job_id}/exclude")
def exclude(job_id: str, body: ExcludeRequest) -> dict:
    return store.exclude(job_id, body.image_ids).to_dict()


@app.get("/api/jobs/{job_id}/thumbs/{image_id}")
def thumbnail(job_id: str, image_id: str) -> Response:
    try:
        data = store.thumbnail_jpeg(job_id, image_id)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not thumbnail: {exc}") from exc
    return Response(content=data, media_type="image/jpeg")


@app.get("/api/jobs/{job_id}/images/{image_id}")
def original_image(job_id: str, image_id: str) -> FileResponse:
    img = store.image(job_id, image_id)
    suffix = img.path.suffix.lower()
    media = _IMAGE_TYPES.get(suffix, "application/octet-stream")
    return FileResponse(
        path=img.path,
        media_type=media,
        headers={"Content-Disposition": f'inline; filename="{img.filename}"'},
    )


@app.get("/api/jobs/{job_id}/export.zip")
def export_zip(job_id: str) -> Response:
    data = store.build_zip(job_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="clonebins.zip"'},
    )


def _mount_web_ui() -> None:
    dist = os.environ.get("CLONEBINS_WEB_DIST")
    if not dist:
        return
    directory = Path(dist)
    if directory.is_dir():
        app.mount("/", StaticFiles(directory=str(directory), html=True), name="web")


_mount_web_ui()


def run(host: str | None = None, port: int | None = None) -> None:
    import uvicorn

    bind_host = host or os.environ.get("CLONEBINS_API_HOST", "127.0.0.1")
    bind_port = port if port is not None else int(os.environ.get("CLONEBINS_API_PORT", "8765"))
    uvicorn.run("clonebins_api.main:app", host=bind_host, port=bind_port, reload=False)
