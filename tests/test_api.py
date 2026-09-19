from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from clonebins_api.main import app
from portraits import write_identity_set

client = TestClient(app)


def _wait(job_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        last = client.get(f"/api/jobs/{job_id}").json()
        if last["status"] in {"done", "error", "cancelled"}:
            return last
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish: {last}")


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["privacy"] == "local"


def test_upload_cluster_rename_zip(tmp_path: Path):
    write_identity_set(tmp_path)
    files = []
    for path in sorted(tmp_path.glob("*.png")):
        files.append(("files", (path.name, path.read_bytes(), "image/png")))
    files.append(("files", ("corrupt.jpg", b"not-an-image", "image/jpeg")))

    created = client.post("/api/jobs/upload", files=files)
    assert created.status_code == 200, created.text
    job_id = created.json()["id"]

    started = client.post(
        f"/api/jobs/{job_id}/cluster",
        json={
            "mode": "face+body",
            "threshold": 0.45,
            "min_images": 2,
            "download_models": False,
            "subject_prefix": "char",
            "keep_names": True,
        },
    )
    assert started.status_code == 200, started.text
    job = _wait(job_id)
    assert job["status"] == "done", job
    assert len(job["clusters"]) == 2
    skipped = [i for i in job["images"] if i["skipped"]]
    assert len(skipped) == 1
    assert skipped[0]["filename"] == "corrupt.jpg"

    first = job["clusters"][0]
    assert first["included"] is False
    renamed = client.patch(
        f"/api/jobs/{job_id}/clusters/{first['id']}",
        json={"name": "hero_main"},
    )
    assert renamed.status_code == 200
    names = {c["name"] for c in renamed.json()["clusters"]}
    assert "hero_main" in names

    empty_zip = client.get(f"/api/jobs/{job_id}/export.zip")
    assert empty_zip.status_code == 400

    included = client.post(f"/api/jobs/{job_id}/include-all", json={"included": True})
    assert included.status_code == 200
    assert all(c["included"] for c in included.json()["clusters"])

    original = client.get(f"/api/jobs/{job_id}/images/{first['image_ids'][0]}")
    assert original.status_code == 200
    assert original.headers["content-type"] in {"image/png", "image/jpeg"}

    thumb = client.get(f"/api/jobs/{job_id}/thumbs/{first['image_ids'][0]}")
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/jpeg"

    zipped = client.get(f"/api/jobs/{job_id}/export.zip")
    assert zipped.status_code == 200, zipped.text
    archive = zipfile.ZipFile(io.BytesIO(zipped.content))
    members = archive.namelist()
    folders = {m.split("/")[0] for m in members}
    assert "hero_main" in folders
    assert any(name.endswith(".png") for name in members)
    assert all("corrupt" not in name for name in members)


def test_from_path_and_merge(tmp_path: Path):
    write_identity_set(tmp_path)
    created = client.post("/api/jobs/from-path", json={"path": str(tmp_path)})
    assert created.status_code == 200, created.text
    job_id = created.json()["id"]
    client.post(
        f"/api/jobs/{job_id}/cluster",
        json={"mode": "face+body", "download_models": False, "min_images": 2},
    )
    job = _wait(job_id)
    assert job["status"] == "done"
    ids = [c["id"] for c in job["clusters"]]
    assert len(ids) == 2
    client.post(f"/api/jobs/{job_id}/include-all", json={"included": True})
    merged = client.post(f"/api/jobs/{job_id}/merge", json={"cluster_ids": ids})
    assert merged.status_code == 200
    body = merged.json()
    assert len(body["clusters"]) == 1
    assert body["clusters"][0]["image_ids"].__len__() == 6
