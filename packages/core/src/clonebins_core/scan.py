"""Scan an input tree for supported image files."""

from __future__ import annotations

from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def scan_images(input_dir: Path, *, recursive: bool = True) -> list[Path]:
    """Return sorted image paths. Does not open files (corrupt checks happen later)."""
    root = input_dir.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {root}")

    if recursive:
        candidates = (p for p in root.rglob("*") if p.is_file())
    else:
        candidates = (p for p in root.iterdir() if p.is_file())

    images = [p for p in candidates if p.suffix.lower() in IMAGE_EXTENSIONS]
    images.sort()
    return images
