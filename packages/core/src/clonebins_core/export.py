"""Write clustered images into subject folders."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from clonebins_core.types import ClusterPlan, Naming, Placement

_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")


def safe_folder_name(name: str) -> str:
    cleaned = _UNSAFE.sub("_", name.strip()).strip("._-")
    return cleaned or "subject"


def safe_prefix(prefix: str) -> str:
    return safe_folder_name(prefix)


def subject_name(prefix: str, index: int, total: int) -> str:
    width = max(2, len(str(max(total, 1))))
    return f"{safe_prefix(prefix)}_{index:0{width}d}"


def export_plan(
    plan: ClusterPlan,
    output_dir: Path,
    *,
    placement: Placement = Placement.COPY,
    naming: Naming = Naming.KEEP,
) -> list[Path]:
    """Create output folders and place files. Returns destination paths written."""
    dest_root = output_dir.expanduser().resolve()
    dest_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for cluster in plan.clusters:
        folder = dest_root / cluster.name
        folder.mkdir(parents=True, exist_ok=True)
        used_names: set[str] = set()
        for i, member in enumerate(cluster.members, start=1):
            dest = _destination(folder, member.path, i, naming, used_names)
            _place(member.path, dest, placement)
            written.append(dest)
    return written


def _destination(
    folder: Path,
    source: Path,
    index: int,
    naming: Naming,
    used_names: set[str],
) -> Path:
    suffix = source.suffix.lower() or ".jpg"
    if naming is Naming.INDEX:
        name = f"{index:05d}{suffix}"
    else:
        name = source.name
        if name in used_names:
            stem = source.stem
            n = 2
            while True:
                candidate = f"{stem}_{n}{suffix}"
                if candidate not in used_names:
                    name = candidate
                    break
                n += 1
    used_names.add(name)
    return folder / name


def _place(source: Path, dest: Path, placement: Placement) -> None:
    if dest.exists():
        dest.unlink()
    if placement is Placement.HARDLINK:
        try:
            dest.hardlink_to(source)
            return
        except OSError:
            # Cross-device or unsupported FS: copy instead.
            shutil.copy2(source, dest)
            return
    shutil.copy2(source, dest)
