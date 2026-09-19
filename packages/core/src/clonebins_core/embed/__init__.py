"""Embedding backends: YuNet+SFace faces, lightweight body/appearance, optional InsightFace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass
class EmbedResult:
    embedding: np.ndarray | None
    faces_found: int = 0
    used_face: bool = False
    used_body: bool = False
    note: str | None = None


class Embedder(Protocol):
    name: str

    def embed(self, image_bgr: np.ndarray) -> EmbedResult:
        """Return an L2-normalized embedding, or None if the image cannot be represented."""
        ...


def l2_normalize(vec: np.ndarray) -> np.ndarray:
    arr = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-12:
        return arr
    return arr / norm


def combine_embeddings(face: np.ndarray, body: np.ndarray, *, face_weight: float = 0.75) -> np.ndarray:
    """Weighted concat of face + appearance, then L2-normalize."""
    face_n = l2_normalize(face) * float(face_weight)
    body_n = l2_normalize(body) * float(1.0 - face_weight)
    return l2_normalize(np.concatenate([face_n, body_n]))


def stack_embeddings(vectors: list[np.ndarray]) -> np.ndarray:
    """Stack 1-D embeddings, left-padding shorter rows so mixed face / appearance
    lengths still form a matrix. Numpy ``stack`` raises ``ValueError: all input
    arrays must have the same shape`` when YuNet misses a face in ``face+body``.
    """
    if not vectors:
        return np.zeros((0, 0), dtype=np.float32)
    flats = [l2_normalize(v) for v in vectors]
    max_dim = max(int(v.size) for v in flats)
    if max_dim == 0:
        return np.zeros((len(flats), 0), dtype=np.float32)
    rows = []
    for vec in flats:
        if vec.size == max_dim:
            rows.append(vec)
        elif vec.size < max_dim:
            # Face sits in the prefix of a combined vector; appearance-only rows
            # are the shorter suffix, so pad zeros on the left.
            rows.append(np.pad(vec.astype(np.float32, copy=False), (max_dim - vec.size, 0)))
        else:
            rows.append(vec[:max_dim])
    return np.stack(rows, axis=0)
