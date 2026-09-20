"""Embedding backends: YuNet+SFace faces, lightweight body/appearance, optional InsightFace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np


@dataclass
class EmbedResult:
    embedding: np.ndarray | None
    faces_found: int = 0
    used_face: bool = False
    used_body: bool = False
    note: str | None = None
    # Parts are stored so face+body can be re-aligned after a mixed folder:
    # some images have a face vector, others only appearance, and dims may
    # only be known after the first successful face hit.
    face_embedding: np.ndarray | None = None
    body_embedding: np.ndarray | None = None


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


def combine_embeddings(
    face: np.ndarray, body: np.ndarray, *, face_weight: float = 0.75
) -> np.ndarray:
    """Weighted concat of face + appearance, then L2-normalize."""
    face_n = l2_normalize(face) * float(face_weight)
    body_n = l2_normalize(body) * float(1.0 - face_weight)
    return l2_normalize(np.concatenate([face_n, body_n]))


def pad_to_dim(vec: np.ndarray | None, dim: int) -> np.ndarray:
    """Return a 1-D float32 vector of length ``dim`` (zeros if ``vec`` is missing)."""
    if dim <= 0:
        return np.zeros(0, dtype=np.float32)
    if vec is None:
        return np.zeros(int(dim), dtype=np.float32)
    flat = np.asarray(vec, dtype=np.float32).reshape(-1)
    n = int(flat.size)
    if n == dim:
        return flat
    if n < dim:
        return np.pad(flat, (0, int(dim) - n))
    return flat[: int(dim)]


def stack_embeddings(vectors: list[np.ndarray]) -> np.ndarray:
    """Stack 1-D embeddings, left-padding shorter rows so mixed face / appearance
    lengths still form a matrix. Numpy ``stack`` raises ``ValueError: all input
    arrays must have the same shape`` when YuNet misses a face in ``face+body``.

    Prefer :func:`build_embedding_matrix` when face/body parts are available —
    that keeps the face prefix and appearance suffix aligned across rows.
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


def _part_dim(vectors: Sequence[np.ndarray | None], declared: int | None) -> int:
    observed = [int(np.asarray(v).reshape(-1).size) for v in vectors if v is not None]
    if observed:
        return max(observed)
    if declared is not None and declared > 0:
        return int(declared)
    return 0


def build_embedding_matrix(
    records: Sequence[object],
    *,
    face_weight: float = 0.75,
    declared_face_dim: int | None = None,
    declared_body_dim: int | None = None,
) -> np.ndarray:
    """Build a 2-D matrix with a single column count from mixed face / body parts.

    Each record may expose ``face_embedding``, ``body_embedding``, and/or
    ``embedding``. When parts exist, missing faces become a zero prefix of the
    observed face dimension so every row is ``[face | body]`` with identical
    length *before* clustering. Combined-only records fall back to
    :func:`stack_embeddings`.
    """
    if not records:
        return np.zeros((0, 0), dtype=np.float32)

    faces = [getattr(r, "face_embedding", None) for r in records]
    bodies = [getattr(r, "body_embedding", None) for r in records]
    combined = [getattr(r, "embedding", None) for r in records]
    has_parts = any(v is not None for v in faces + bodies)

    if not has_parts:
        present = [v for v in combined if v is not None]
        return stack_embeddings(present)

    face_dim = _part_dim(faces, declared_face_dim)
    body_dim = _part_dim(bodies, declared_body_dim)

    rows: list[np.ndarray] = []
    for record, face, body, fallback in zip(records, faces, bodies, combined, strict=True):
        if face is None and body is None:
            vec = l2_normalize(fallback) if fallback is not None else np.zeros(
                face_dim + body_dim, dtype=np.float32
            )
        elif face_dim == 0:
            vec = l2_normalize(pad_to_dim(body, body_dim))
        elif body_dim == 0:
            vec = l2_normalize(pad_to_dim(face, face_dim))
        else:
            vec = combine_embeddings(
                pad_to_dim(face, face_dim),
                pad_to_dim(body, body_dim),
                face_weight=face_weight,
            )
        if hasattr(record, "embedding"):
            record.embedding = vec
        rows.append(vec)

    if not rows:
        return np.zeros((0, 0), dtype=np.float32)
    # Final equalize in case a combined-only fallback had a different length.
    return stack_embeddings(rows)
