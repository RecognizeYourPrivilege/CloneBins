"""FastAPI app: local-only clustering API for the Vite UI."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import uuid
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
    ModelDownloadRequest,
    PathRequest,
    RenameRequest,
    ShareRequest,
)
from clonebins_api.shares import ShareError, ShareSpec, probe_share
from clonebins_core.models import (
    INSTALL_COMMAND,
    catalog_status,
    curl_install_script,
    default_models_dir,
    download_missing_face_models,
    missing_model_specs,
    models_present,
    user_home,
)

app = FastAPI(
    title="CloneBins API",
    version=__version__,
    description="Local clustering API. Images stay on this machine.",
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


class _ModelTask:
    def __init__(self) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.status = "running"
        self.logs: list[str] = []
        self.error: str | None = None
        self.lock = threading.Lock()

    def log(self, message: str) -> None:
        with self.lock:
            self.logs.append(message)

    def snapshot(self) -> dict:
        with self.lock:
            directory = default_models_dir()
            catalog = catalog_status(directory)
            missing = missing_model_specs(directory)
            return {
                "id": self.id,
                "status": self.status,
                "logs": list(self.logs),
                "error": self.error,
                "models_dir": str(directory),
                "missing": missing,
                "missing_count": len(missing),
                "catalog": catalog,
            }


_model_tasks: dict[str, _ModelTask] = {}
_model_tasks_lock = threading.Lock()


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
    """Verify which YuNet / SFace ONNX files are present vs missing."""
    return _models_payload()


@app.post("/api/models/download")
def models_download(body: ModelDownloadRequest) -> dict:
    """Download YuNet/SFace ONNX files. Always starts; Verify is not required.

    Poll GET /api/models/download/{id} for logs. Uses urllib+certifi, then
    system curl if the frozen sidecar cannot complete TLS.
    """
    task = _ModelTask()
    with _model_tasks_lock:
        _model_tasks[task.id] = task
    thread = threading.Thread(target=_run_model_download, args=(task, body), daemon=True)
    thread.start()
    return task.snapshot()


@app.get("/api/models/install-command")
def models_install_command() -> dict:
    directory = default_models_dir()
    return {
        "command": INSTALL_COMMAND,
        "models_dir": str(directory),
        "home": str(user_home()),
        "curl_script": curl_install_script(directory),
    }


@app.post("/api/models/open-folder")
def models_open_folder() -> dict:
    directory = default_models_dir()
    directory.mkdir(parents=True, exist_ok=True)
    opened = _open_directory(directory)
    return {
        "ok": opened,
        "models_dir": str(directory),
        "home": str(user_home()),
        "command": INSTALL_COMMAND,
    }


@app.get("/api/models/download/{task_id}")
def models_download_status(task_id: str) -> dict:
    with _model_tasks_lock:
        task = _model_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Download task not found")
    return task.snapshot()


def _run_model_download(task: _ModelTask, body: ModelDownloadRequest) -> None:
    directory = default_models_dir()
    catalog = catalog_status(directory)
    missing = missing_model_specs(directory)
    task.log(f"Cache {directory} (home {catalog['home']})")
    expected = catalog["expected"]
    n_yunet = catalog["yunet_count"]
    n_sface = catalog["sface_count"]
    task.log(f"Catalog {expected} ONNX files ({n_yunet} YuNet + {n_sface} SFace)")
    for family in ("yunet", "sface"):
        for item in catalog[family]:
            mark = "ready" if item["ready"] else "MISSING"
            task.log(f"  {family} {item['id']}: {mark}  {item['filename']}")
    if not missing and not body.force:
        task.log("Every catalogued YuNet / SFace file is already present.")
        task.log("Nothing to download. Use force to re-fetch.")
        task.log(f"CLI fallback: {INSTALL_COMMAND}")
        with task.lock:
            task.status = "done"
        return
    if body.force:
        task.log("Force: re-downloading catalog files even if they look valid.")
    if missing:
        names = ", ".join(item["filename"] for item in missing)
        task.log(f"Missing {len(missing)} file(s): {names}")
    try:
        download_missing_face_models(
            models_dir=directory,
            log=task.log,
            all_variants=body.all_variants,
            force=body.force,
            yunet_id=body.yunet,
            sface_id=body.sface,
        )
        leftover = missing_model_specs(directory)
        if leftover:
            task.log("Still missing: " + ", ".join(item["filename"] for item in leftover))
            task.log(f"CLI fallback: {INSTALL_COMMAND}")
            with task.lock:
                task.status = "error"
                task.error = "Some models could not be downloaded"
        else:
            task.log(f"All {expected} ONNX files are on disk in {directory}")
            with task.lock:
                task.status = "done"
    except Exception as exc:
        task.log(f"Error: {exc}")
        task.log(f"CLI fallback: {INSTALL_COMMAND}")
        with task.lock:
            task.status = "error"
            task.error = str(exc)


def _open_directory(path: Path) -> bool:
    if sys.platform == "darwin":
        cmd = ["open", str(path)]
    elif sys.platform == "win32":
        cmd = ["explorer", str(path)]
    else:
        cmd = ["xdg-open", str(path)]
    try:
        subprocess.run(cmd, check=False, timeout=15, capture_output=True)
        return True
    except Exception:
        return False


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
