"""Download and cache local face models (YuNet detector + SFace recognizer).

opencv_zoo ships three YuNet detectors and three SFace recognizers. All six
load through OpenCV's FaceDetectorYN / FaceRecognizerSF:

YuNet 2023 (detector)
  2023mar        FP32 — highest quality, default
  2023mar_int8   INT8 — smaller/faster, tiny AP drop
  2023mar_int8bq INT8 block-quant — near-FP32 AP, smaller than FP32

SFace 2021 (recognizer, 128-D embeddings)
  2021dec        FP32 — highest quality, default
  2021dec_int8   INT8 — smaller/faster
  2021dec_int8bq INT8 block-quant — near-FP32 accuracy, smaller than FP32
"""

from __future__ import annotations

import argparse
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ENV_MODELS_DIR = "CLONEBINS_MODELS_DIR"

HF_YUNET = "https://huggingface.co/opencv/face_detection_yunet/resolve/main"
HF_SFACE = "https://huggingface.co/opencv/face_recognition_sface/resolve/main"
GH_YUNET = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet"
GH_SFACE = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface"
GH_RAW_YUNET = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet"
GH_RAW_SFACE = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface"


def _urls(*parts: str) -> tuple[str, ...]:
    return tuple(parts)


@dataclass(frozen=True)
class OnnxSpec:
    id: str
    filename: str
    label: str
    family: str  # "yunet" | "sface"
    urls: tuple[str, ...]
    min_bytes: int
    notes: str


YUNET_MODELS: tuple[OnnxSpec, ...] = (
    OnnxSpec(
        id="2023mar",
        filename="face_detection_yunet_2023mar.onnx",
        label="YuNet 2023 FP32",
        family="yunet",
        urls=_urls(
            f"{HF_YUNET}/face_detection_yunet_2023mar.onnx",
            f"{GH_YUNET}/face_detection_yunet_2023mar.onnx",
            f"{GH_RAW_YUNET}/face_detection_yunet_2023mar.onnx",
        ),
        min_bytes=50_000,
        notes="Default detector. Best quality; WIDER Face AP ≈ 0.88 / 0.87 / 0.75.",
    ),
    OnnxSpec(
        id="2023mar_int8",
        filename="face_detection_yunet_2023mar_int8.onnx",
        label="YuNet 2023 INT8",
        family="yunet",
        urls=_urls(
            f"{HF_YUNET}/face_detection_yunet_2023mar_int8.onnx",
            f"{GH_YUNET}/face_detection_yunet_2023mar_int8.onnx",
            f"{GH_RAW_YUNET}/face_detection_yunet_2023mar_int8.onnx",
        ),
        min_bytes=40_000,
        notes="Quantized detector. Faster/smaller; AP drop is ~0.003 on easy.",
    ),
    OnnxSpec(
        id="2023mar_int8bq",
        filename="face_detection_yunet_2023mar_int8bq.onnx",
        label="YuNet 2023 INT8-BQ",
        family="yunet",
        urls=_urls(
            f"{HF_YUNET}/face_detection_yunet_2023mar_int8bq.onnx",
            f"{GH_YUNET}/face_detection_yunet_2023mar_int8bq.onnx",
            f"{GH_RAW_YUNET}/face_detection_yunet_2023mar_int8bq.onnx",
        ),
        min_bytes=40_000,
        notes="Block-quantized detector (block_size=64). Near-FP32 AP, smaller file.",
    ),
)

SFACE_MODELS: tuple[OnnxSpec, ...] = (
    OnnxSpec(
        id="2021dec",
        filename="face_recognition_sface_2021dec.onnx",
        label="SFace 2021 FP32",
        family="sface",
        urls=_urls(
            f"{HF_SFACE}/face_recognition_sface_2021dec.onnx",
            f"{GH_SFACE}/face_recognition_sface_2021dec.onnx",
            f"{GH_RAW_SFACE}/face_recognition_sface_2021dec.onnx",
        ),
        min_bytes=1_000_000,
        notes="Default recognizer. 128-D embeddings; eval accuracy ≈ 0.9940.",
    ),
    OnnxSpec(
        id="2021dec_int8",
        filename="face_recognition_sface_2021dec_int8.onnx",
        label="SFace 2021 INT8",
        family="sface",
        urls=_urls(
            f"{HF_SFACE}/face_recognition_sface_2021dec_int8.onnx",
            f"{GH_SFACE}/face_recognition_sface_2021dec_int8.onnx",
            f"{GH_RAW_SFACE}/face_recognition_sface_2021dec_int8.onnx",
        ),
        min_bytes=1_000_000,
        notes="Quantized recognizer. Faster/smaller; accuracy ≈ 0.9932.",
    ),
    OnnxSpec(
        id="2021dec_int8bq",
        filename="face_recognition_sface_2021dec_int8bq.onnx",
        label="SFace 2021 INT8-BQ",
        family="sface",
        urls=_urls(
            f"{HF_SFACE}/face_recognition_sface_2021dec_int8bq.onnx",
            f"{GH_SFACE}/face_recognition_sface_2021dec_int8bq.onnx",
            f"{GH_RAW_SFACE}/face_recognition_sface_2021dec_int8bq.onnx",
        ),
        min_bytes=1_000_000,
        notes="Block-quantized recognizer. Near-FP32 accuracy (≈ 0.9942), ~11MB.",
    ),
)

DEFAULT_YUNET_ID = "2023mar"
DEFAULT_SFACE_ID = "2021dec"

# Backward-compatible names used by older docs / caches.
YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
SFACE_FILENAME = "face_recognition_sface_2021dec.onnx"
YUNET_MIN_BYTES = 50_000
SFACE_MIN_BYTES = 1_000_000


class ModelDownloadError(RuntimeError):
    """Raised when face models cannot be located or downloaded."""


@dataclass(frozen=True)
class FaceModelPaths:
    yunet: Path
    sface: Path
    yunet_id: str = DEFAULT_YUNET_ID
    sface_id: str = DEFAULT_SFACE_ID


def _index(specs: tuple[OnnxSpec, ...]) -> dict[str, OnnxSpec]:
    return {spec.id: spec for spec in specs}


YUNET_BY_ID = _index(YUNET_MODELS)
SFACE_BY_ID = _index(SFACE_MODELS)


def default_models_dir() -> Path:
    override = os.environ.get(ENV_MODELS_DIR)
    if override:
        return Path(override).expanduser().resolve()
    return Path.home().joinpath(".cache", "clonebins", "models")


def yunet_spec(yunet_id: str = DEFAULT_YUNET_ID) -> OnnxSpec:
    try:
        return YUNET_BY_ID[yunet_id]
    except KeyError as exc:
        known = ", ".join(YUNET_BY_ID)
        raise ModelDownloadError(f"Unknown YuNet id {yunet_id!r}. Choose: {known}") from exc


def sface_spec(sface_id: str = DEFAULT_SFACE_ID) -> OnnxSpec:
    try:
        return SFACE_BY_ID[sface_id]
    except KeyError as exc:
        known = ", ".join(SFACE_BY_ID)
        raise ModelDownloadError(f"Unknown SFace id {sface_id!r}. Choose: {known}") from exc


def models_present(
    models_dir: Path | None = None,
    *,
    yunet_id: str = DEFAULT_YUNET_ID,
    sface_id: str = DEFAULT_SFACE_ID,
) -> bool:
    paths = resolve_model_paths(models_dir, yunet_id=yunet_id, sface_id=sface_id)
    return _looks_valid(paths.yunet, yunet_spec(yunet_id).min_bytes) and _looks_valid(
        paths.sface, sface_spec(sface_id).min_bytes
    )


def resolve_model_paths(
    models_dir: Path | None = None,
    *,
    yunet_id: str = DEFAULT_YUNET_ID,
    sface_id: str = DEFAULT_SFACE_ID,
) -> FaceModelPaths:
    root = models_dir or default_models_dir()
    yunet = yunet_spec(yunet_id)
    sface = sface_spec(sface_id)
    return FaceModelPaths(
        yunet=root / yunet.filename,
        sface=root / sface.filename,
        yunet_id=yunet.id,
        sface_id=sface.id,
    )


def catalog_status(models_dir: Path | None = None) -> dict:
    root = models_dir or default_models_dir()
    return {
        "models_dir": str(root),
        "yunet": [_spec_status(spec, root) for spec in YUNET_MODELS],
        "sface": [_spec_status(spec, root) for spec in SFACE_MODELS],
        "default_yunet": DEFAULT_YUNET_ID,
        "default_sface": DEFAULT_SFACE_ID,
    }


def _spec_status(spec: OnnxSpec, root: Path) -> dict:
    path = root / spec.filename
    ready = _looks_valid(path, spec.min_bytes)
    return {
        "id": spec.id,
        "filename": spec.filename,
        "label": spec.label,
        "notes": spec.notes,
        "ready": ready,
        "bytes": path.stat().st_size if path.is_file() else 0,
    }


def ensure_face_models(
    *,
    models_dir: Path | None = None,
    download: bool = True,
    log=None,
    yunet_id: str = DEFAULT_YUNET_ID,
    sface_id: str = DEFAULT_SFACE_ID,
) -> FaceModelPaths:
    """Return local model paths, downloading on first use when allowed."""
    paths = resolve_model_paths(models_dir, yunet_id=yunet_id, sface_id=sface_id)
    paths.yunet.parent.mkdir(parents=True, exist_ok=True)

    needed: list[tuple[Path, OnnxSpec]] = []
    yunet = yunet_spec(yunet_id)
    sface = sface_spec(sface_id)
    if not _looks_valid(paths.yunet, yunet.min_bytes):
        needed.append((paths.yunet, yunet))
    if not _looks_valid(paths.sface, sface.min_bytes):
        needed.append((paths.sface, sface))

    if not needed:
        return paths
    if not download:
        missing = ", ".join(spec.filename for _, spec in needed)
        raise ModelDownloadError(
            f"Face models missing ({missing}) in {paths.yunet.parent}. "
            "Run `clonebins models download` once (requires network), "
            "or set CLONEBINS_MODELS_DIR to a folder that already contains them."
        )

    for dest, spec in needed:
        if log:
            log(f"Downloading {spec.filename} …")
        _download_first_ok(spec.urls, dest, min_bytes=spec.min_bytes)
        if log:
            log(f"Saved {dest}")

    return paths


def download_all_face_models(*, models_dir: Path | None = None, log=None) -> Path:
    """Fetch every YuNet + SFace variant into the models directory."""
    root = models_dir or default_models_dir()
    root.mkdir(parents=True, exist_ok=True)
    for spec in (*YUNET_MODELS, *SFACE_MODELS):
        dest = root / spec.filename
        if _looks_valid(dest, spec.min_bytes):
            if log:
                log(f"Already present: {dest.name}")
            continue
        if log:
            log(f"Downloading {spec.filename} …")
        _download_first_ok(spec.urls, dest, min_bytes=spec.min_bytes)
        if log:
            log(f"Saved {dest}")
    return root


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
    raise ModelDownloadError(f"Could not download {dest.name}. Tried:\n  " + "\n  ".join(errors))


def _download_url(url: str, dest: Path, timeout: int = 180) -> None:
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


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download CloneBins face ONNX weights.")
    parser.add_argument("--dir", type=Path, default=None)
    parser.add_argument("--all", action="store_true", help="Download every YuNet and SFace variant.")
    parser.add_argument("--yunet", default=DEFAULT_YUNET_ID)
    parser.add_argument("--sface", default=DEFAULT_SFACE_ID)
    args = parser.parse_args(argv)
    directory = args.dir or default_models_dir()
    if args.all:
        download_all_face_models(models_dir=directory, log=print)
    else:
        ensure_face_models(
            models_dir=directory,
            download=True,
            log=print,
            yunet_id=args.yunet,
            sface_id=args.sface,
        )
    print(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
