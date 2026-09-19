from __future__ import annotations

import numpy as np

from clonebins_core.embed import EmbedResult, combine_embeddings, stack_embeddings
from clonebins_core.embed.appearance import AppearanceEmbedder
from clonebins_core.embed.factory import HybridEmbedder
from clonebins_core.pipeline import PipelineConfig, run_pipeline
from clonebins_core.types import ClusterMode
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


def test_stack_embeddings_pads_mixed_lengths():
    long = np.ones(6, dtype=np.float32)
    short = np.ones(2, dtype=np.float32)
    matrix = stack_embeddings([long, short])
    assert matrix.shape == (2, 6)
    assert np.allclose(matrix[1, :4], 0.0)


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


def test_combine_then_stack_matches_placeholder():
    face = np.ones(4, dtype=np.float32)
    body = np.arange(5, dtype=np.float32) + 1
    combined = combine_embeddings(face, body)
    missing = combine_embeddings(np.zeros(4, dtype=np.float32), body)
    matrix = stack_embeddings([combined, missing])
    assert matrix.shape == (2, 9)
