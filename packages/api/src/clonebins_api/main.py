"""FastAPI app: local-only clustering API for the Vite UI."""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

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
)
from clonebins_core.models import default_models_dir, models_present

app = FastAPI(
    title="CloneBins API",
    version=__version__,
    description="Local clustering API. Images stay on this machine.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(JobError)
def _job_error(_request, exc: JobError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)


@app.get("/api/health")
def health() -> dict:
    directory = default_models_dir()
    return {
        "ok": True,
        "version": __version__,
        "privacy": "local",
        "models_dir": str(directory),
        "models_ready": models_present(directory),
    }


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


@app.get("/api/jobs/{job_id}/export.zip")
def export_zip(job_id: str) -> Response:
    data = store.build_zip(job_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="clonebins.zip"'},
    )


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    uvicorn.run("clonebins_api.main:app", host=host, port=port, reload=False)
