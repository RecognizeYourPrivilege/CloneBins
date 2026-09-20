"""In-memory job store: upload/path → clonebins_core.pipeline → zip."""

from __future__ import annotations

import io
import shutil
import tempfile
import threading
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from clonebins_api.schemas import ClusterSettings
from clonebins_api.shares import ShareError, ShareSpec, fetch_share
from clonebins_core.export import safe_folder_name
from clonebins_core.pipeline import PipelineConfig, run_pipeline
from clonebins_core.scan import IMAGE_EXTENSIONS
from clonebins_core.types import ClusterMode, Naming, Placement

JOBS_ROOT = Path(tempfile.gettempdir()) / "clonebins-jobs"
MAX_UPLOAD_FILES = 500
MAX_UPLOAD_BYTES = 40 * 1024 * 1024


class JobError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class JobImage:
    id: str
    path: Path
    filename: str
    skipped: bool = False
    skip_reason: str | None = None
    unmatched: bool = False
    unmatched_reason: str | None = None


@dataclass
class JobCluster:
    id: str
    name: str
    image_ids: list[str] = field(default_factory=list)
    included: bool = False
    below_min: bool = False


class JobProgress:
    def __init__(self, cancel: threading.Event) -> None:
        self.cancel = cancel
        self.phase = ""
        self.completed = 0
        self.total = 0
        self.detail = ""
        self.logs: list[str] = []
        self._lock = threading.Lock()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "phase": self.phase,
                "completed": self.completed,
                "total": self.total,
                "detail": self.detail,
                "logs": list(self.logs[-40:]),
            }

    def _check_cancel(self) -> None:
        if self.cancel.is_set():
            raise KeyboardInterrupt

    def log(self, message: str) -> None:
        self._check_cancel()
        with self._lock:
            self.logs.append(message)

    def start(self, phase: str, total: int | None = None) -> None:
        self._check_cancel()
        with self._lock:
            self.phase = phase
            self.completed = 0
            self.total = int(total or 0)
            self.detail = ""

    def advance(self, phase: str, step: int = 1, message: str = "") -> None:
        self._check_cancel()
        with self._lock:
            self.phase = phase
            self.completed += step
            if message:
                self.detail = message

    def finish(self, phase: str) -> None:
        self._check_cancel()
        with self._lock:
            self.phase = phase
            if self.total:
                self.completed = self.total
            self.detail = "done"


@dataclass
class Job:
    id: str
    root: Path
    input_dir: Path
    source: str  # "upload" | "path"
    status: str = "ready"
    error: str | None = None
    settings: ClusterSettings | None = None
    images: dict[str, JobImage] = field(default_factory=dict)
    clusters: list[JobCluster] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    backend_name: str = ""
    scanned: int = 0
    cancel: threading.Event = field(default_factory=threading.Event)
    progress: JobProgress = field(init=False)
    lock: threading.Lock = field(default_factory=threading.Lock)
    worker: threading.Thread | None = None

    def __post_init__(self) -> None:
        self.progress = JobProgress(self.cancel)

    def to_dict(self) -> dict:
        with self.lock:
            return {
                "id": self.id,
                "status": self.status,
                "source": self.source,
                "settings": self.settings.model_dump() if self.settings else None,
                "progress": self.progress.snapshot(),
                "clusters": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "image_ids": list(c.image_ids),
                        "included": c.included,
                        "below_min": c.below_min,
                    }
                    for c in self.clusters
                ],
                "images": [
                    {
                        "id": img.id,
                        "filename": img.filename,
                        "skipped": img.skipped,
                        "skip_reason": img.skip_reason,
                        "unmatched": img.unmatched,
                        "unmatched_reason": img.unmatched_reason,
                    }
                    for img in self.images.values()
                ],
                "notes": list(self.notes),
                "backend_name": self.backend_name,
                "scanned": self.scanned,
                "error": self.error,
            }


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_upload(self, files: list[tuple[str, bytes]]) -> Job:
        if not files:
            raise JobError("No files uploaded")
        if len(files) > MAX_UPLOAD_FILES:
            raise JobError(f"Too many files (max {MAX_UPLOAD_FILES})")
        job = self._new_job(source="upload")
        used: set[str] = set()
        saved = 0
        for original_name, data in files:
            if len(data) > MAX_UPLOAD_BYTES:
                continue
            name = Path(original_name).name
            suffix = Path(name).suffix.lower()
            if suffix not in IMAGE_EXTENSIONS:
                continue
            dest_name = _unique_name(name, used)
            dest = job.input_dir / dest_name
            dest.write_bytes(data)
            saved += 1
        if saved == 0:
            shutil.rmtree(job.root, ignore_errors=True)
            raise JobError("No jpg/jpeg/png/webp files in upload")
        return job

    def create_from_path(self, raw_path: str) -> Job:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_dir():
            raise JobError(f"Not a directory: {path}")
        job = self._new_job(source="path", input_dir=path)
        return job

    def create_from_share(self, spec: ShareSpec) -> Job:
        job = self._new_job(source="share")
        logs: list[str] = []

        def log(message: str) -> None:
            logs.append(message)

        try:
            fetch_share(spec, job.input_dir, log=log)
        except ShareError:
            shutil.rmtree(job.root, ignore_errors=True)
            with self._lock:
                self._jobs.pop(job.id, None)
            raise
        finally:
            spec.clear_secrets()
        with job.lock:
            job.notes = list(logs)
        return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobError("Job not found", status_code=404)
        return job

    def start_cluster(self, job_id: str, settings: ClusterSettings) -> Job:
        job = self.get(job_id)
        with job.lock:
            if job.status == "clustering":
                raise JobError("Clustering already running", status_code=409)
            job.status = "clustering"
            job.error = None
            job.cancel.clear()
            job.settings = settings
            job.progress = JobProgress(job.cancel)
            job.clusters = []
            job.images = {}
            job.notes = []
        thread = threading.Thread(target=self._run_cluster, args=(job, settings), daemon=True)
        job.worker = thread
        thread.start()
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        job.cancel.set()
        with job.lock:
            if job.status == "clustering":
                job.status = "cancelled"
        return job

    def rename(self, job_id: str, cluster_id: str, name: str) -> Job:
        job = self.get(job_id)
        cleaned = safe_folder_name(name)
        with job.lock:
            cluster = _cluster(job, cluster_id)
            existing = {c.name for c in job.clusters if c.id != cluster_id}
            cluster.name = _unique_cluster_name(cleaned, existing)
        return job

    def set_included(self, job_id: str, cluster_id: str, included: bool) -> Job:
        job = self.get(job_id)
        with job.lock:
            _cluster(job, cluster_id).included = included
        return job

    def set_included_all(self, job_id: str, included: bool) -> Job:
        job = self.get(job_id)
        with job.lock:
            for cluster in job.clusters:
                cluster.included = included
        return job

    def merge(self, job_id: str, cluster_ids: list[str]) -> Job:
        if len(cluster_ids) < 2:
            raise JobError("Select at least two clusters to merge")
        job = self.get(job_id)
        with job.lock:
            primary = _cluster(job, cluster_ids[0])
            was_included = any(_cluster(job, cid).included for cid in cluster_ids)
            seen = set(primary.image_ids)
            keep = {cluster_ids[0]}
            for cid in cluster_ids[1:]:
                other = _cluster(job, cid)
                for image_id in other.image_ids:
                    if image_id not in seen:
                        primary.image_ids.append(image_id)
                        seen.add(image_id)
                keep.add(cid)
            job.clusters = [c for c in job.clusters if c.id == primary.id or c.id not in keep]
            primary.below_min = False
            primary.included = was_included
        return job

    def extract(self, job_id: str, cluster_id: str, image_ids: list[str]) -> Job:
        if not image_ids:
            raise JobError("Select images to split into a new bin")
        job = self.get(job_id)
        with job.lock:
            source = _cluster(job, cluster_id)
            move = [i for i in image_ids if i in source.image_ids]
            if not move:
                raise JobError("Those images are not in this cluster")
            if len(move) >= len(source.image_ids):
                raise JobError("Leave at least one image in the original bin")
            source.image_ids = [i for i in source.image_ids if i not in set(move)]
            existing = {c.name for c in job.clusters}
            new = JobCluster(
                id=_new_id("c"),
                name=_unique_cluster_name("split", existing),
                image_ids=move,
                included=source.included,
            )
            job.clusters.append(new)
        return job

    def exclude(self, job_id: str, image_ids: list[str]) -> Job:
        job = self.get(job_id)
        drop = set(image_ids)
        with job.lock:
            for cluster in job.clusters:
                cluster.image_ids = [i for i in cluster.image_ids if i not in drop]
            job.clusters = [c for c in job.clusters if c.image_ids]
        return job

    def image(self, job_id: str, image_id: str) -> JobImage:
        job = self.get(job_id)
        img = job.images.get(image_id)
        if img is None or not img.path.is_file():
            raise JobError("Image not found", status_code=404)
        return img

    def thumbnail_jpeg(self, job_id: str, image_id: str, size: int = 192) -> bytes:
        img = self.image(job_id, image_id)
        with Image.open(img.path) as im:
            im = im.convert("RGB")
            im.thumbnail((size, size))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=82)
            return buf.getvalue()

    def build_zip(self, job_id: str) -> bytes:
        job = self.get(job_id)
        with job.lock:
            if job.status == "clustering":
                raise JobError("Clustering is still running", status_code=409)
            keep_names = True if job.settings is None else job.settings.keep_names
            clusters = [c for c in job.clusters if c.included and c.image_ids]
            images = dict(job.images)
        if not clusters:
            raise JobError("No included clusters to export")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for cluster in clusters:
                folder = safe_folder_name(cluster.name)
                used: set[str] = set()
                for index, image_id in enumerate(cluster.image_ids, start=1):
                    member = images.get(image_id)
                    if member is None or not member.path.is_file():
                        continue
                    suffix = member.path.suffix.lower() or ".jpg"
                    if keep_names:
                        name = _unique_name(member.filename, used)
                    else:
                        name = f"{index:05d}{suffix}"
                        used.add(name)
                    zf.write(member.path, f"{folder}/{name}")
        return buf.getvalue()

    def _new_job(self, *, source: str, input_dir: Path | None = None) -> Job:
        job_id = uuid.uuid4().hex[:12]
        root = JOBS_ROOT / job_id
        stored_input = root / "input"
        stored_input.mkdir(parents=True, exist_ok=True)
        job = Job(
            id=job_id,
            root=root,
            input_dir=input_dir or stored_input,
            source=source,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def _run_cluster(self, job: Job, settings: ClusterSettings) -> None:
        try:
            mode = ClusterMode.FACE if settings.mode == "face" else ClusterMode.FACE_BODY
            plan = run_pipeline(
                PipelineConfig(
                    input_dir=job.input_dir,
                    output_dir=job.root / "unused-output",
                    mode=mode,
                    threshold=settings.threshold,
                    min_images=settings.min_images,
                    dry_run=True,
                    placement=Placement.COPY,
                    naming=Naming.KEEP if settings.keep_names else Naming.INDEX,
                    subject_prefix=settings.subject_prefix,
                    download_models=settings.download_models,
                    yunet_id=settings.yunet,
                    sface_id=settings.sface,
                ),
                progress=job.progress,
            )
            images: dict[str, JobImage] = {}
            clusters: list[JobCluster] = []

            def add_record(record) -> str:
                image_id = _new_id("i")
                images[image_id] = JobImage(
                    id=image_id,
                    path=record.path,
                    filename=record.path.name,
                    skipped=record.skipped,
                    skip_reason=record.skip_reason,
                    unmatched=record.unmatched,
                    unmatched_reason=record.unmatched_reason,
                )
                return image_id

            for bin_ in plan.clusters:
                clusters.append(
                    JobCluster(
                        id=_new_id("c"),
                        name=bin_.name,
                        image_ids=[add_record(m) for m in bin_.members],
                        included=False,
                        below_min=False,
                    )
                )
            for bin_ in plan.dropped:
                clusters.append(
                    JobCluster(
                        id=_new_id("c"),
                        name=bin_.name.replace("_dropped", "small"),
                        image_ids=[add_record(m) for m in bin_.members],
                        included=False,
                        below_min=True,
                    )
                )
            for record in plan.unmatched:
                add_record(record)
            for record in plan.skipped:
                add_record(record)

            with job.lock:
                if job.cancel.is_set():
                    job.status = "cancelled"
                else:
                    job.status = "done"
                job.images = images
                job.clusters = clusters
                job.notes = list(plan.notes)
                job.backend_name = plan.backend_name
                job.scanned = plan.scanned
        except KeyboardInterrupt:
            with job.lock:
                job.status = "cancelled"
                job.error = "Cancelled"
        except Exception as exc:
            with job.lock:
                job.status = "error"
                job.error = str(exc)


def _cluster(job: Job, cluster_id: str) -> JobCluster:
    for cluster in job.clusters:
        if cluster.id == cluster_id:
            return cluster
    raise JobError("Cluster not found", status_code=404)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _unique_name(name: str, used: set[str]) -> str:
    if name not in used:
        used.add(name)
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix
    n = 2
    while True:
        candidate = f"{stem}_{n}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        n += 1


def _unique_cluster_name(name: str, existing: set[str]) -> str:
    if name not in existing:
        return name
    n = 2
    while f"{name}_{n}" in existing:
        n += 1
    return f"{name}_{n}"


store = JobStore()
