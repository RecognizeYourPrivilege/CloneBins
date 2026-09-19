"""Optional InsightFace backend (buffalo). Not used unless explicitly requested.

Install extra deps: ``pip install 'clonebins-core[insightface]'``
then pass ``face_backend='insightface'`` into the pipeline later.
"""

from __future__ import annotations

import numpy as np

from clonebins_core.embed import EmbedResult, l2_normalize


class InsightFaceEmbedder:
    name = "insightface"
    embedding_dim = 512

    def __init__(self, model_name: str = "buffalo_s") -> None:
        try:
            from insightface.app import FaceAnalysis  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "InsightFace is not installed. "
                "pip install 'clonebins-core[insightface]' to enable this backend."
            ) from exc

        self._app = FaceAnalysis(name=model_name, providers=["CPUExecutionProvider"])
        self._app.prepare(ctx_id=-1, det_size=(640, 640))

    def embed(self, image_bgr: np.ndarray) -> EmbedResult:
        faces = self._app.get(image_bgr)
        if not faces:
            return EmbedResult(embedding=None, faces_found=0)
        faces = sorted(faces, key=lambda f: float((f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])))
        best = faces[-1]
        embedding = getattr(best, "normed_embedding", None)
        if embedding is None:
            embedding = getattr(best, "embedding", None)
        if embedding is None:
            return EmbedResult(embedding=None, faces_found=len(faces))
        return EmbedResult(
            embedding=l2_normalize(np.asarray(embedding, dtype=np.float32)),
            faces_found=len(faces),
            used_face=True,
        )
