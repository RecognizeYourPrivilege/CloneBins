"""Build the embedder for a clustering run."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from clonebins_core.embed import Embedder, EmbedResult, combine_embeddings, l2_normalize
from clonebins_core.embed.appearance import AppearanceEmbedder
from clonebins_core.embed.sface import SFaceEmbedder
from clonebins_core.models import ensure_face_models
from clonebins_core.types import ClusterMode


class HybridEmbedder:
    """Face (optional) + appearance. Missing faces fall back per mode."""

    def __init__(
        self,
        *,
        mode: ClusterMode,
        face: Embedder | None,
        body: Embedder,
        fallback_note: str | None = None,
    ) -> None:
        self.mode = mode
        self.face = face
        self.body = body
        self.fallback_note = fallback_note
        self._face_dim: int | None = (
            getattr(face, "embedding_dim", None) if face is not None else None
        )
        self._body_dim: int | None = getattr(body, "embedding_dim", None)
        if face is not None:
            self.name = f"{face.name}+{body.name}" if mode is ClusterMode.FACE_BODY else face.name
        else:
            self.name = body.name

    @property
    def face_dim(self) -> int | None:
        return self._face_dim

    @property
    def body_dim(self) -> int | None:
        return self._body_dim

    def _face_placeholder(self) -> np.ndarray:
        dim = self._face_dim
        if dim is None or dim <= 0:
            # SFace is 128-D; used only until a real face vector is seen.
            dim = 128
        return np.zeros(int(dim), dtype=np.float32)

    def _remember_dims(self, face_vec: np.ndarray | None, body_vec: np.ndarray | None) -> None:
        if face_vec is not None:
            self._face_dim = int(np.asarray(face_vec).reshape(-1).size)
        if body_vec is not None:
            self._body_dim = int(np.asarray(body_vec).reshape(-1).size)

    def embed(self, image_bgr: np.ndarray) -> EmbedResult:
        body_res = self.body.embed(image_bgr)
        face_res = self.face.embed(image_bgr) if self.face is not None else EmbedResult(None)
        face_vec = None if face_res.embedding is None else l2_normalize(face_res.embedding)
        body_vec = None if body_res.embedding is None else l2_normalize(body_res.embedding)
        self._remember_dims(face_vec, body_vec)

        if self.mode is ClusterMode.FACE:
            if face_vec is None:
                return EmbedResult(
                    embedding=None,
                    faces_found=face_res.faces_found,
                    used_face=False,
                    used_body=False,
                    note="no face detected" if self.face is not None else "face models unavailable",
                    face_embedding=None,
                    body_embedding=None,
                )
            return EmbedResult(
                embedding=face_vec,
                faces_found=face_res.faces_found,
                used_face=True,
                used_body=False,
                face_embedding=face_vec,
                body_embedding=None,
            )

        # face+body: every usable row must have the same length. Returning a
        # bare appearance vector when YuNet misses a face made np.stack raise
        # "all input arrays must have the same shape" on mixed folders.
        if body_vec is None:
            return EmbedResult(
                embedding=None,
                faces_found=face_res.faces_found,
                face_embedding=face_vec,
                body_embedding=None,
            )

        if self.face is None:
            return EmbedResult(
                embedding=body_vec,
                faces_found=face_res.faces_found,
                used_face=False,
                used_body=True,
                note=self.fallback_note or "appearance only (no face model)",
                face_embedding=None,
                body_embedding=body_vec,
            )

        if face_vec is not None:
            combined = combine_embeddings(face_vec, body_vec)
            return EmbedResult(
                embedding=combined,
                faces_found=face_res.faces_found,
                used_face=True,
                used_body=True,
                face_embedding=face_vec,
                body_embedding=body_vec,
            )
        combined = combine_embeddings(self._face_placeholder(), body_vec)
        return EmbedResult(
            embedding=combined,
            faces_found=face_res.faces_found,
            used_face=False,
            used_body=True,
            note="appearance only (no face)",
            face_embedding=None,
            body_embedding=body_vec,
        )


def build_embedder(
    mode: ClusterMode,
    *,
    download_models: bool = True,
    models_dir: Path | None = None,
    log=None,
    yunet_id: str = "2023mar",
    sface_id: str = "2021dec",
) -> tuple[HybridEmbedder, list[str]]:
    """Construct the default embedder. Face models are optional with a fallback."""
    notes: list[str] = []
    appearance = AppearanceEmbedder()
    face: Embedder | None = None
    try:
        paths = ensure_face_models(
            models_dir=models_dir,
            download=download_models,
            log=log,
            yunet_id=yunet_id,
            sface_id=sface_id,
        )
        face = SFaceEmbedder(paths)
    except Exception as exc:
        # OpenCV may raise cv2.error if the ONNX graph is incompatible.
        notes.append(
            f"Face backend unavailable ({type(exc).__name__}). "
            "Using appearance embedding only. Run `clonebins models download` "
            "for YuNet + SFace identity clustering."
        )
        if mode is ClusterMode.FACE:
            notes.append(
                "Mode is `face` but no face model is loaded; images without a "
                "face embedding will be unmatched. Prefer `--mode face+body` "
                "until models are installed."
            )
    embedder = HybridEmbedder(mode=mode, face=face, body=appearance)
    return embedder, notes
