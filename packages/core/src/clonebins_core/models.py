"""Download and cache local face models (YuNet detector + SFace recognizer)."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
SFACE_FILENAME = "face_recognition_sface_2021dec.onnx"

# Multiple mirrors: opencv_zoo uses Git LFS for SFace, so GitHub "raw" is not enough.
YUNET_URLS = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
)

SFACE_URLS = (
    "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx",
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
)

# Rough lower bounds so we reject truncated HTML error pages.
YUNET_MIN_BYTES = 50_000
SFACE_MIN_BYTES = 1_000_000

ENV_MODELS_DIR = "CLONEBINS_MODELS_DIR"


class ModelDownloadError(RuntimeError):
    """Raised when face models cannot be located or downloaded."""


@dataclass(frozen=True)
class FaceModelPaths:
    yunet: Path
    sface: Path


def default_models_dir() -> Path:
    override = os.environ.get(ENV_MODELS_DIR)
    if override:
        return Path(override).expanduser().resolve()
    return Path.home().joinpath(".cache", "clonebins", "models")


def models_present(models_dir: Path | None = None) -> bool:
    paths = resolve_model_paths(models_dir)
    return _looks_valid(paths.yunet, YUNET_MIN_BYTES) and _looks_valid(paths.sface, SFACE_MIN_BYTES)


def resolve_model_paths(models_dir: Path | None = None) -> FaceModelPaths:
    root = models_dir or default_models_dir()
    return FaceModelPaths(yunet=root / YUNET_FILENAME, sface=root / SFACE_FILENAME)


def ensure_face_models(
    *,
    models_dir: Path | None = None,
    download: bool = True,
    log=None,
) -> FaceModelPaths:
    """Return local model paths, downloading on first use when allowed."""
    paths = resolve_model_paths(models_dir)
    paths.yunet.parent.mkdir(parents=True, exist_ok=True)

    needed: list[tuple[Path, tuple[str, ...], int]] = []
    if not _looks_valid(paths.yunet, YUNET_MIN_BYTES):
        needed.append((paths.yunet, YUNET_URLS, YUNET_MIN_BYTES))
    if not _looks_valid(paths.sface, SFACE_MIN_BYTES):
        needed.append((paths.sface, SFACE_URLS, SFACE_MIN_BYTES))

    if not needed:
        return paths
    if not download:
        missing = ", ".join(p.name for p, _, _ in needed)
        raise ModelDownloadError(
            f"Face models missing ({missing}) in {paths.yunet.parent}. "
            "Run `clonebins models download` once (requires network), "
            "or set CLONEBINS_MODELS_DIR to a folder that already contains them."
        )

    for dest, urls, min_bytes in needed:
        if log:
            log(f"Downloading {dest.name} …")
        _download_first_ok(urls, dest, min_bytes=min_bytes)
        if log:
            log(f"Saved {dest}")

    return paths


def _looks_valid(path: Path, min_bytes: int) -> bool:
    try:
        return path.is_file() and path.stat().st_size >= min_bytes
    except OSError:
        return False


def _download_first_ok(urls: tuple[str, ...], dest: Path, *, min_bytes: int) -> None:
    errors: list[str] = []
    dest.parent.mkdir(parents=True, exist_ok=True)
    for url in urls:
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        try:
            _download_url(url, tmp)
            size = tmp.stat().st_size
            if size < min_bytes:
                tmp.unlink(missing_ok=True)
                errors.append(f"{url} (too small: {size} bytes)")
                continue
            tmp.replace(dest)
            return
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            tmp.unlink(missing_ok=True)
            errors.append(f"{url} ({exc})")
    raise ModelDownloadError(
        f"Could not download {dest.name}. Tried:\n  " + "\n  ".join(errors)
    )


def _download_url(url: str, dest: Path, timeout: int = 120) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CloneBins/0.1 (local dataset clustering)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response, dest.open("wb") as handle:
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            handle.write(chunk)
