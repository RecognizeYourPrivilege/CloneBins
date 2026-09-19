"""Load images in a corrupt-tolerant way (never raises for a single bad file)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

try:
    import cv2
except ImportError:  # pragma: no cover - opencv is a hard dep, but keep a message
    cv2 = None  # type: ignore[assignment]


def load_image_bgr(path: Path) -> np.ndarray:
    """Load an image as BGR uint8. Raises ValueError if unreadable."""
    if not path.is_file():
        raise ValueError("not a file")
    if path.stat().st_size == 0:
        raise ValueError("empty file")

    data = path.read_bytes()
    if cv2 is not None:
        arr = np.frombuffer(data, dtype=np.uint8)
        decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if decoded is not None and decoded.size > 0:
            return decoded

    try:
        with Image.open(path) as img:
            img.load()
            rgb = img.convert("RGB")
            array = np.array(rgb, dtype=np.uint8)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"unreadable image: {exc}") from exc

    if array.size == 0:
        raise ValueError("decoded empty image")
    # RGB -> BGR
    return array[:, :, ::-1].copy()
