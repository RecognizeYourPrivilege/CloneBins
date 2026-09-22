"""Download and cache local face models (YuNet detector + SFace recognizer).

opencv_zoo ships four YuNet detectors and three SFace recognizers. All seven
load through OpenCV's FaceDetectorYN / FaceRecognizerSF:

YuNet (detector)
  2023mar        FP32 — highest quality, default in CloneBins
  2023mar_int8   INT8 — smaller/faster, tiny AP drop
  2023mar_int8bq INT8 block-quant — near-FP32 AP, smaller than FP32
  2026may        Dynamic H/W re-export of 2023mar (opencv_zoo default as of 2026-05)

SFace 2021 (recognizer, 128-D embeddings)
  2021dec        FP32 — highest quality, default
  2021dec_int8   INT8 — smaller/faster
  2021dec_int8bq INT8 block-quant — near-FP32 accuracy, smaller than FP32
"""

from __future__ import annotations

import argparse
import os
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ENV_MODELS_DIR = "CLONEBINS_MODELS_DIR"
ENV_BUNDLED_MODELS = "CLONEBINS_BUNDLED_MODELS"
INSTALL_COMMAND = "clonebins models download --force"
USER_AGENT = "CloneBins/1.0.0 (local dataset clustering)"

HF_YUNET = "https://huggingface.co/opencv/face_detection_yunet/resolve/main"
HF_SFACE = "https://huggingface.co/opencv/face_recognition_sface/resolve/main"
GH_YUNET = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet"
GH_SFACE = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface"
GH_RAW_YUNET = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet"
GH_RAW_SFACE = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface"
GH_RAWREF_YUNET = (
    "https://github.com/opencv/opencv_zoo/raw/refs/heads/main/models/face_detection_yunet"
)
GH_RAWREF_SFACE = (
    "https://github.com/opencv/opencv_zoo/raw/refs/heads/main/models/face_recognition_sface"
)
JSDELIVR_YUNET = "https://cdn.jsdelivr.net/gh/opencv/opencv_zoo@main/models/face_detection_yunet"
JSDELIVR_SFACE = "https://cdn.jsdelivr.net/gh/opencv/opencv_zoo@main/models/face_recognition_sface"

CATALOG_SIZE = 7


def _pack_urls(
    hf_base: str,
    gh_base: str,
    gh_raw_base: str,
    filename: str,
    *,
    gh_rawref_base: str,
    jsdelivr_base: str,
) -> tuple[str, ...]:
    hf = f"{hf_base}/{filename}"
    return (
        f"{hf}?download=true",
        hf,
        f"{gh_base}/{filename}",
        f"{gh_raw_base}/{filename}",
        f"{gh_rawref_base}/{filename}",
        f"{jsdelivr_base}/{filename}",
    )


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
        urls=_pack_urls(
            HF_YUNET,
            GH_YUNET,
            GH_RAW_YUNET,
            "face_detection_yunet_2023mar.onnx",
            gh_rawref_base=GH_RAWREF_YUNET,
            jsdelivr_base=JSDELIVR_YUNET,
        ),
        min_bytes=50_000,
        notes="Default detector. Best quality; WIDER Face AP ≈ 0.88 / 0.87 / 0.75.",
    ),
    OnnxSpec(
        id="2023mar_int8",
        filename="face_detection_yunet_2023mar_int8.onnx",
        label="YuNet 2023 INT8",
        family="yunet",
        urls=_pack_urls(
            HF_YUNET,
            GH_YUNET,
            GH_RAW_YUNET,
            "face_detection_yunet_2023mar_int8.onnx",
            gh_rawref_base=GH_RAWREF_YUNET,
            jsdelivr_base=JSDELIVR_YUNET,
        ),
        min_bytes=40_000,
        notes="Quantized detector. Faster/smaller; AP drop is ~0.003 on easy.",
    ),
    OnnxSpec(
        id="2023mar_int8bq",
        filename="face_detection_yunet_2023mar_int8bq.onnx",
        label="YuNet 2023 INT8-BQ",
        family="yunet",
        urls=_pack_urls(
            HF_YUNET,
            GH_YUNET,
            GH_RAW_YUNET,
            "face_detection_yunet_2023mar_int8bq.onnx",
            gh_rawref_base=GH_RAWREF_YUNET,
            jsdelivr_base=JSDELIVR_YUNET,
        ),
        min_bytes=40_000,
        notes="Block-quantized detector (block_size=64). Near-FP32 AP, smaller file.",
    ),
    OnnxSpec(
        id="2026may",
        filename="face_detection_yunet_2026may.onnx",
        label="YuNet 2026 dynamic",
        family="yunet",
        urls=_pack_urls(
            HF_YUNET,
            GH_YUNET,
            GH_RAW_YUNET,
            "face_detection_yunet_2026may.onnx",
            gh_rawref_base=GH_RAWREF_YUNET,
            jsdelivr_base=JSDELIVR_YUNET,
        ),
        min_bytes=50_000,
        notes=(
            "Dynamic H/W re-export of 2023mar (opencv_zoo default). "
            "HF may 404; GitHub LFS is the source."
        ),
    ),
)

SFACE_MODELS: tuple[OnnxSpec, ...] = (
    OnnxSpec(
        id="2021dec",
        filename="face_recognition_sface_2021dec.onnx",
        label="SFace 2021 FP32",
        family="sface",
        urls=_pack_urls(
            HF_SFACE,
            GH_SFACE,
            GH_RAW_SFACE,
            "face_recognition_sface_2021dec.onnx",
            gh_rawref_base=GH_RAWREF_SFACE,
            jsdelivr_base=JSDELIVR_SFACE,
        ),
        min_bytes=1_000_000,
        notes="Default recognizer. 128-D embeddings; eval accuracy ≈ 0.9940.",
    ),
    OnnxSpec(
        id="2021dec_int8",
        filename="face_recognition_sface_2021dec_int8.onnx",
        label="SFace 2021 INT8",
        family="sface",
        urls=_pack_urls(
            HF_SFACE,
            GH_SFACE,
            GH_RAW_SFACE,
            "face_recognition_sface_2021dec_int8.onnx",
            gh_rawref_base=GH_RAWREF_SFACE,
            jsdelivr_base=JSDELIVR_SFACE,
        ),
        min_bytes=1_000_000,
        notes="Quantized recognizer. Faster/smaller; accuracy ≈ 0.9932.",
    ),
    OnnxSpec(
        id="2021dec_int8bq",
        filename="face_recognition_sface_2021dec_int8bq.onnx",
        label="SFace 2021 INT8-BQ",
        family="sface",
        urls=_pack_urls(
            HF_SFACE,
            GH_SFACE,
            GH_RAW_SFACE,
            "face_recognition_sface_2021dec_int8bq.onnx",
            gh_rawref_base=GH_RAWREF_SFACE,
            jsdelivr_base=JSDELIVR_SFACE,
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
ALL_MODELS: tuple[OnnxSpec, ...] = (*YUNET_MODELS, *SFACE_MODELS)
EXPECTED_FILENAMES: tuple[str, ...] = tuple(spec.filename for spec in ALL_MODELS)


def user_home() -> Path:
    """Resolve the real login home (same directory shell ``~`` expands to).

    Frozen macOS sidecars sometimes inherit an empty or literal ``~`` HOME.
    Prefer a usable HOME/USERPROFILE (so we match the user's shell), then the
    passwd database, then Path.home(). Never return an unexpanded ``~``.
    """
    for key in ("HOME", "USERPROFILE"):
        raw = (os.environ.get(key) or "").strip()
        if not raw or raw == "~":
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute() or "~" in path.parts:
            continue
        return path
    try:
        import pwd

        path = Path(pwd.getpwuid(os.getuid()).pw_dir)
        if path.is_absolute() and "~" not in path.parts:
            return path
    except (ImportError, KeyError, OSError):
        pass
    try:
        path = Path.home()
        if path.is_absolute() and "~" not in path.parts:
            return path
    except RuntimeError:
        pass
    return Path.cwd().resolve()


def default_models_dir() -> Path:
    """``$HOME/.cache/clonebins/models``, or ``CLONEBINS_MODELS_DIR`` if set.

    Home is expanded on every platform (including macOS). Linux-only
    ``/home/...`` paths are never hardcoded.
    """
    override = os.environ.get(ENV_MODELS_DIR)
    if override:
        return Path(override).expanduser().resolve()
    return (user_home() / ".cache" / "clonebins" / "models").resolve()


def _norm_dir(path: Path) -> Path:
    expanded = path.expanduser()
    try:
        return expanded.resolve(strict=False)
    except (OSError, RuntimeError):
        return expanded


def bundled_models_dirs() -> list[Path]:
    """Directories that may hold ONNX files shipped inside the app.

    Search order matches packaging:
    ``CLONEBINS_BUNDLED_MODELS``, PyInstaller extract dir, next to the
    executable (Windows zip / NSIS ``models/``), macOS
    ``Contents/Resources/models``, Linux ``/usr/share/clonebins/models`` and
    Tauri's ``/usr/lib/<exe>/models``, then the repo
    ``apps/desktop/resources/models`` folder filled at package time.
    """
    seen: set[Path] = set()
    ordered: list[Path] = []

    def add(path: Path | None) -> None:
        if path is None:
            return
        try:
            resolved = _norm_dir(path)
        except (OSError, RuntimeError, ValueError):
            return
        if resolved in seen:
            return
        seen.add(resolved)
        ordered.append(resolved)

    override = (os.environ.get(ENV_BUNDLED_MODELS) or "").strip()
    if override:
        add(Path(override))

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        add(Path(meipass) / "models")

    try:
        exe = Path(sys.executable).resolve()
    except OSError:
        exe = None
    if exe is not None:
        add(exe.parent / "models")
        add(exe.parent / "resources" / "models")
        if exe.parent.name == "MacOS":
            add(exe.parent.parent / "Resources" / "models")
        # Tauri dev/release layout: target/(debug|release)/../lib/<exe>/models
        if exe.parent.name in {"release", "debug"}:
            add(exe.parent.parent / "lib" / exe.name / "models")

    appdir = (os.environ.get("APPDIR") or "").strip()
    lib_names = ("clonebins-desktop", "CloneBins", "clonebins")
    if appdir:
        app_root = Path(appdir)
        add(app_root / "usr" / "share" / "clonebins" / "models")
        for name in lib_names:
            add(app_root / "usr" / "lib" / name / "models")
    add(Path("/usr/share/clonebins/models"))
    for name in lib_names:
        add(Path("/usr/lib") / name / "models")

    here = Path(__file__).resolve()
    if len(here.parents) > 4:
        add(here.parents[4] / "apps" / "desktop" / "resources" / "models")
    return ordered


def find_bundled_file(spec: OnnxSpec) -> Path | None:
    """Return a baked copy of ``spec`` that already looks like a real ONNX file."""
    for directory in bundled_models_dirs():
        candidate = directory / spec.filename
        if _looks_valid(candidate, spec.min_bytes):
            return candidate
    return None


def copy_bundled_into_cache(
    models_dir: Path | None = None,
    *,
    log=None,
) -> list[str]:
    """Copy baked ONNX files into the user cache when the cache file is missing.

    Files already valid in the cache are left untouched. Returns filenames copied.
    """
    root = models_dir or default_models_dir()
    root.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for spec in ALL_MODELS:
        dest = root / spec.filename
        if _looks_valid(dest, spec.min_bytes):
            continue
        src = find_bundled_file(spec)
        if src is None:
            continue
        try:
            if src.resolve() == dest.resolve():
                continue
        except OSError:
            pass
        if log:
            log(f"Copying baked {spec.filename} from {src.parent}")
        tmp = dest.with_suffix(dest.suffix + ".copytmp")
        try:
            shutil.copy2(src, tmp)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            if log:
                log(f"Could not copy baked {spec.filename}: {exc}")
            continue
        if not _looks_valid(tmp, spec.min_bytes):
            tmp.unlink(missing_ok=True)
            continue
        tmp.replace(dest)
        copied.append(spec.filename)
        if log:
            log(f"Cached baked model {dest} ({dest.stat().st_size} bytes)")
    return copied


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
    yunet = [_spec_status(spec, root) for spec in YUNET_MODELS]
    sface = [_spec_status(spec, root) for spec in SFACE_MODELS]
    missing = [item for item in (*yunet, *sface) if not item["ready"]]
    return {
        "home": str(user_home()),
        "models_dir": str(root),
        "yunet": yunet,
        "sface": sface,
        "expected": CATALOG_SIZE,
        "yunet_count": len(YUNET_MODELS),
        "sface_count": len(SFACE_MODELS),
        "default_yunet": DEFAULT_YUNET_ID,
        "default_sface": DEFAULT_SFACE_ID,
        "all_ready": not missing,
    }


def _spec_status(spec: OnnxSpec, root: Path) -> dict:
    path = root / spec.filename
    ready = _looks_valid(path, spec.min_bytes)
    bundled = find_bundled_file(spec)
    return {
        "id": spec.id,
        "filename": spec.filename,
        "label": spec.label,
        "notes": spec.notes,
        "ready": ready,
        "bundled": bundled is not None,
        "bytes": path.stat().st_size if path.is_file() else 0,
        "path": str(path),
        "source": spec.urls[0],
        "family": spec.family,
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

    if needed:
        copy_bundled_into_cache(paths.yunet.parent, log=log)
        needed = []
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
            "Run `clonebins models verify` to copy baked weights and download "
            "only what is still missing, or set CLONEBINS_MODELS_DIR to a folder "
            "that already contains them."
        )

    for dest, spec in needed:
        if log:
            log(f"Downloading {spec.filename} …")
        _download_first_ok(spec.urls, dest, min_bytes=spec.min_bytes)
        if log:
            log(f"Saved {dest}")

    return paths


def missing_model_specs(models_dir: Path | None = None) -> list[dict]:
    """Catalog entries that are not on disk yet (or too small to be valid)."""
    catalog = catalog_status(models_dir)
    return [item for family in ("yunet", "sface") for item in catalog[family] if not item["ready"]]


def download_missing_face_models(
    *,
    models_dir: Path | None = None,
    log=None,
    all_variants: bool = True,
    force: bool = False,
    yunet_id: str = DEFAULT_YUNET_ID,
    sface_id: str = DEFAULT_SFACE_ID,
) -> Path:
    """Download catalog files. Valid cache hits are skipped unless ``force``."""
    if all_variants:
        return download_all_face_models(models_dir=models_dir, log=log, force=force)
    if force:
        paths = resolve_model_paths(models_dir, yunet_id=yunet_id, sface_id=sface_id)
        for path in (paths.yunet, paths.sface):
            path.unlink(missing_ok=True)
    ensure_face_models(
        models_dir=models_dir,
        download=True,
        log=log,
        yunet_id=yunet_id,
        sface_id=sface_id,
    )
    return models_dir or default_models_dir()


def verify_and_fill_face_models(
    *, models_dir: Path | None = None, log=None, force: bool = False
) -> Path:
    """Check the user cache, copy baked weights, then download only gaps.

    Preference order: files already in the cache, models shipped inside the
    app bundle, then the network for anything still missing. ``force`` skips
    the cache and baked copy and re-fetches every catalog file.
    """
    root = models_dir or default_models_dir()
    root.mkdir(parents=True, exist_ok=True)
    if log:
        log(f"Verify cache {root} (home {user_home()})")
        baked = [str(path) for path in bundled_models_dirs() if path.is_dir()]
        log("Baked dirs: " + (", ".join(baked) if baked else "(none)"))
    if not force:
        copied = copy_bundled_into_cache(root, log=log)
        if log and not copied:
            log("No baked files needed copying (cache already had them, or none are bundled).")
    catalog = catalog_status(root)
    if log:
        log(
            f"Catalog {catalog['expected']} ONNX files "
            f"({catalog['yunet_count']} YuNet + {catalog['sface_count']} SFace)"
        )
        for family in ("yunet", "sface"):
            for item in catalog[family]:
                if item["ready"]:
                    mark = "ready"
                elif item.get("bundled"):
                    mark = "baked, not yet cached"
                else:
                    mark = "MISSING"
                log(f"  {family} {item['id']}: {mark}  {item['filename']}")
    return download_all_face_models(models_dir=root, log=log, force=force)


def download_all_face_models(
    *, models_dir: Path | None = None, log=None, force: bool = False
) -> Path:
    """Fetch every YuNet + SFace variant into the models directory.

    Unless ``force``, valid cache files are kept and missing files are filled
    from the baked app bundle before any network request.
    """
    root = models_dir or default_models_dir()
    root.mkdir(parents=True, exist_ok=True)
    if not force:
        copy_bundled_into_cache(root, log=log)
    if log:
        log(f"Writing {CATALOG_SIZE} ONNX files into {root}")
        log(f"Fallback CLI: {INSTALL_COMMAND}")
    total = len(ALL_MODELS)
    for index, spec in enumerate(ALL_MODELS, start=1):
        dest = root / spec.filename
        if not force and _looks_valid(dest, spec.min_bytes):
            if log:
                log(f"[{index}/{total}] Already present: {dest.name}")
            continue
        if log:
            action = "Re-downloading" if force and dest.exists() else "Downloading"
            log(f"[{index}/{total}] {action} {spec.filename}")
        _download_first_ok(spec.urls, dest, min_bytes=spec.min_bytes, log=log)
        if log:
            size = dest.stat().st_size if dest.is_file() else 0
            log(f"[{index}/{total}] Saved {dest} ({size} bytes)")
    leftover = [
        spec.filename
        for spec in ALL_MODELS
        if not _looks_valid(root / spec.filename, spec.min_bytes)
    ]
    if leftover:
        raise ModelDownloadError("Still missing after download: " + ", ".join(leftover))
    return root


def _looks_valid(path: Path, min_bytes: int) -> bool:
    try:
        return path.is_file() and path.stat().st_size >= min_bytes and _looks_like_onnx(path)
    except OSError:
        return False


def _looks_like_onnx(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return False
    if len(head) < 8:
        return False
    if head[:1] in {b"<", b"{", b"#"} or head.startswith(b"<!") or head.startswith(b"version https://"):
        return False
    return True


def _download_first_ok(urls: tuple[str, ...], dest: Path, *, min_bytes: int, log=None) -> None:
    errors: list[str] = []
    dest.parent.mkdir(parents=True, exist_ok=True)
    fetchers = (
        ("urllib+certifi", _download_url),
        ("curl", _download_url_curl),
    )
    for url in urls:
        for method, fetch in fetchers:
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            try:
                fetch(url, tmp)
                size = tmp.stat().st_size
                if size < min_bytes or not _looks_like_onnx(tmp):
                    tmp.unlink(missing_ok=True)
                    errors.append(f"{method} {url} (too small or not ONNX: {size} bytes)")
                    continue
                tmp.replace(dest)
                if log:
                    log(f"  ok via {method}: {url}")
                return
            except FileNotFoundError as exc:
                tmp.unlink(missing_ok=True)
                errors.append(f"{method} {url} ({exc})")
            except (
                urllib.error.URLError,
                TimeoutError,
                OSError,
                ValueError,
                subprocess.SubprocessError,
            ) as exc:
                tmp.unlink(missing_ok=True)
                errors.append(f"{method} {url} ({exc})")
    raise ModelDownloadError(f"Could not download {dest.name}. Tried:\n  " + "\n  ".join(errors))


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _download_url(url: str, dest: Path, timeout: int = 180) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/octet-stream,*/*",
        },
    )
    context = _ssl_context()
    with (
        urllib.request.urlopen(request, timeout=timeout, context=context) as response,
        dest.open("wb") as handle,
    ):
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def curl_bin() -> str | None:
    """macOS always ships ``/usr/bin/curl``; use it when frozen urllib SSL fails."""
    for candidate in ("/usr/bin/curl", "/usr/local/bin/curl", "/opt/homebrew/bin/curl"):
        if Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return shutil.which("curl")


def _download_url_curl(url: str, dest: Path, timeout: int = 180) -> None:
    binary = curl_bin()
    if not binary:
        raise FileNotFoundError("curl is not available")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        binary,
        "-L",
        "--fail",
        "--retry",
        "3",
        "--retry-delay",
        "1",
        "--connect-timeout",
        "20",
        "--max-time",
        str(timeout),
        "-A",
        USER_AGENT,
        "-H",
        "Accept: application/octet-stream,*/*",
        "-o",
        str(dest),
        url,
    ]
    completed = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        timeout=timeout + 30,
        text=True,
    )
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip() or f"exit {completed.returncode}"
        dest.unlink(missing_ok=True)
        raise OSError(err)


def curl_install_script(models_dir: Path | None = None) -> str:
    """One-shot ``/usr/bin/curl`` script that writes all seven ONNX files."""
    root = models_dir or default_models_dir()
    curl = curl_bin() or "/usr/bin/curl"
    lines = [f"mkdir -p {root}"]
    for spec in ALL_MODELS:
        # GitHub LFS media URL is the most reliable when Hugging Face 404s.
        url = next((u for u in spec.urls if "media.githubusercontent.com" in u), spec.urls[0])
        dest = root / spec.filename
        lines.append(f'{curl} -L --fail -A "{USER_AGENT}" -o "{dest}" "{url}"')
    return "\n".join(lines)


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download CloneBins face ONNX weights.")
    parser.add_argument("--dir", type=Path, default=None)
    parser.add_argument(
        "--all", action="store_true", help="Download every YuNet and SFace variant."
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-download files even if they look valid."
    )
    parser.add_argument("--yunet", default=DEFAULT_YUNET_ID)
    parser.add_argument("--sface", default=DEFAULT_SFACE_ID)
    args = parser.parse_args(argv)
    directory = args.dir or default_models_dir()
    if args.all:
        download_all_face_models(models_dir=directory, log=print, force=args.force)
    else:
        download_missing_face_models(
            models_dir=directory,
            log=print,
            all_variants=False,
            force=args.force,
            yunet_id=args.yunet,
            sface_id=args.sface,
        )
    print(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
