from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from clonebins_core.embed import (
    EmbedResult,
    build_embedding_matrix,
    combine_embeddings,
    stack_embeddings,
)
from clonebins_core.embed.appearance import AppearanceEmbedder
from clonebins_core.embed.factory import HybridEmbedder
from clonebins_core.pipeline import PipelineConfig, run_pipeline
from clonebins_core.types import ClusterMode, ImageRecord
from portraits import write_identity_set


class _PartialFace:
    """Hits a face only on images whose filename starts with ``red_``."""

    name = "partial-face"
    embedding_dim = 8

    def embed(self, image_bgr: np.ndarray) -> EmbedResult:
        # Bright-red portraits in the fixture have a high red channel.
        if float(image_bgr[:, :, 2].mean()) > 80:
            vec = np.linspace(0.2, 1.0, self.embedding_dim, dtype=np.float32)
            return EmbedResult(embedding=vec, faces_found=1, used_face=True)
        return EmbedResult(embedding=None, faces_found=0)


class _PartialFaceUnknownDim:
    """Same as ``_PartialFace`` but does not advertise ``embedding_dim``.

    A 128-D zero placeholder (SFace default) then an 8-D real face used to
    produce mixed concat lengths and crash ``np.stack``.
    """

    name = "partial-face-unknown-dim"

    def embed(self, image_bgr: np.ndarray) -> EmbedResult:
        if float(image_bgr[:, :, 2].mean()) > 80:
            vec = np.linspace(0.2, 1.0, 8, dtype=np.float32)
            return EmbedResult(embedding=vec, faces_found=1, used_face=True)
        return EmbedResult(embedding=None, faces_found=0)


def test_stack_embeddings_pads_mixed_lengths():
    long = np.ones(6, dtype=np.float32)
    short = np.ones(2, dtype=np.float32)
    matrix = stack_embeddings([long, short])
    assert matrix.shape == (2, 6)
    assert np.allclose(matrix[1, :4], 0.0)


def test_naive_stack_of_face_or_appearance_raises():
    """The original crash: mixed face-concat vs appearance-only rows."""
    face = np.ones(8, dtype=np.float32)
    body = np.arange(5, dtype=np.float32) + 1
    combined = combine_embeddings(face, body)
    appearance_only = body.copy()
    with pytest.raises(ValueError, match="same shape"):
        np.stack([combined, appearance_only])


def test_build_embedding_matrix_aligns_missing_faces():
    body = np.arange(5, dtype=np.float32) + 1
    with_face = ImageRecord(
        path=Path("a.png"),
        relative_name="a.png",
        face_embedding=np.ones(8, dtype=np.float32),
        body_embedding=body,
    )
    no_face = ImageRecord(
        path=Path("b.png"),
        relative_name="b.png",
        face_embedding=None,
        body_embedding=body,
    )
    matrix = build_embedding_matrix([no_face, with_face])
    assert matrix.ndim == 2
    assert matrix.shape[0] == 2
    assert matrix.shape[1] == 8 + 5
    assert matrix.dtype == np.float32
    # Missing-face row is a zero face prefix + appearance (not a shorter vector).
    assert np.allclose(no_face.embedding[:8], 0.0, atol=1e-6)
    assert with_face.embedding.shape == no_face.embedding.shape


def test_face_body_mixed_detection_same_dim(tmp_path):
    """YuNet misses some gens; face+body used to crash np.stack."""
    src = tmp_path / "in"
    write_identity_set(src)
    hybrid = HybridEmbedder(
        mode=ClusterMode.FACE_BODY,
        face=_PartialFace(),
        body=AppearanceEmbedder(),
    )
    results = []
    import cv2

    for path in sorted(src.glob("*.png")):
        image = cv2.imread(str(path))
        results.append(hybrid.embed(image))

    dims = {int(r.embedding.size) for r in results if r.embedding is not None}
    assert len(dims) == 1
    expected = _PartialFace.embedding_dim + AppearanceEmbedder().embedding_dim
    assert dims.pop() == expected
    assert any(r.used_face for r in results)
    assert any(not r.used_face for r in results)

    plan = run_pipeline(
        PipelineConfig(
            input_dir=src,
            output_dir=tmp_path / "out",
            mode=ClusterMode.FACE_BODY,
            min_images=1,
            dry_run=True,
            download_models=False,
            embedder=hybrid,
        )
    )
    assert plan.scanned == 6
    assert not plan.unmatched
    assert plan.clusters or plan.dropped


def test_face_body_unknown_dim_no_face_first(tmp_path):
    """Regression: blue (no face) files sort first; face dim is not declared.

    HybridEmbedder used a 128-D placeholder until the first red portrait, so
    ``np.stack`` / ``vstack`` raised ``all input arrays must have the same shape``.
    """
    src = tmp_path / "in"
    write_identity_set(src)
    hybrid = HybridEmbedder(
        mode=ClusterMode.FACE_BODY,
        face=_PartialFaceUnknownDim(),
        body=AppearanceEmbedder(),
    )
    import cv2

    raw_combined = []
    parts = []
    for path in sorted(src.glob("*.png")):
        image = cv2.imread(str(path))
        result = hybrid.embed(image)
        assert result.embedding is not None
        raw_combined.append(result.embedding)
        parts.append(result)

    # Immediate concat lengths can still differ when the placeholder guessed 128.
    immediate_dims = {int(v.size) for v in raw_combined}
    assert len(immediate_dims) >= 1
    if len(immediate_dims) > 1:
        with pytest.raises(ValueError, match="same shape"):
            np.stack(raw_combined)

    records = [
        ImageRecord(
            path=src / "x",
            relative_name="x",
            embedding=r.embedding,
            face_embedding=r.face_embedding,
            body_embedding=r.body_embedding,
            used_face=r.used_face,
            used_body=r.used_body,
        )
        for r in parts
    ]
    matrix = build_embedding_matrix(records, declared_face_dim=None)
    assert matrix.shape[0] == 6
    assert len({row.size for row in matrix}) == 1
    assert matrix.shape[1] == 8 + AppearanceEmbedder().embedding_dim
    assert any(r.used_face for r in records)
    assert any(not r.used_face for r in records)

    plan = run_pipeline(
        PipelineConfig(
            input_dir=src,
            output_dir=tmp_path / "out",
            mode=ClusterMode.FACE_BODY,
            min_images=1,
            dry_run=True,
            download_models=False,
            embedder=hybrid,
        )
    )
    assert plan.scanned == 6
    assert not plan.unmatched
    clustered = sum(c.size for c in plan.clusters) + sum(c.size for c in plan.dropped)
    assert clustered == 6


def test_combine_then_stack_matches_placeholder():
    face = np.ones(4, dtype=np.float32)
    body = np.arange(5, dtype=np.float32) + 1
    combined = combine_embeddings(face, body)
    missing = combine_embeddings(np.zeros(4, dtype=np.float32), body)
    matrix = stack_embeddings([combined, missing])
    assert matrix.shape == (2, 9)
