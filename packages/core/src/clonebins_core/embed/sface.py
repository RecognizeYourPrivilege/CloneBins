"""YuNet face detector + SFace recognizer via OpenCV (ONNX, local files)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from clonebins_core.embed import EmbedResult, l2_normalize
from clonebins_core.models import FaceModelPaths


class SFaceEmbedder:
    """Default face backend. InsightFace can replace this class later."""

    name = "yunet-sface"
    embedding_dim = 128

    def __init__(self, models: FaceModelPaths, score_threshold: float = 0.6) -> None:
        self.models = models
        self.score_threshold = score_threshold
        if not Path(models.yunet).is_file() or not Path(models.sface).is_file():
            raise FileNotFoundError(f"Face models not found at {models.yunet.parent}")
        # Detector input size is updated per image.
        self._detector = cv2.FaceDetectorYN.create(
            str(models.yunet),
            "",
            (320, 320),
            score_threshold=score_threshold,
            nms_threshold=0.3,
        )
        self._recognizer = cv2.FaceRecognizerSF.create(str(models.sface), "")
        self.name = f"yunet-{models.yunet_id}+sface-{models.sface_id}"

    def embed(self, image_bgr: np.ndarray) -> EmbedResult:
        faces = self._detect(image_bgr)
        if faces is None or len(faces) == 0:
            return EmbedResult(embedding=None, faces_found=0)

        areas = faces[:, 2] * faces[:, 3]
        idx = int(np.argmax(areas))
        face = faces[idx]
        try:
            aligned = self._recognizer.alignCrop(image_bgr, face)
            feature = self._recognizer.feature(aligned)
        except cv2.error:
            return EmbedResult(embedding=None, faces_found=int(len(faces)))

        vec = l2_normalize(np.asarray(feature, dtype=np.float32))
        if vec.size == 0:
            return EmbedResult(embedding=None, faces_found=int(len(faces)))
        return EmbedResult(embedding=vec, faces_found=int(len(faces)), used_face=True)

    def _detect(self, image_bgr: np.ndarray) -> np.ndarray | None:
        height, width = image_bgr.shape[:2]
        if height < 16 or width < 16:
            return None
        # YuNet prefers dimensions that are multiples of 32.
        pad_w = (32 - width % 32) % 32
        pad_h = (32 - height % 32) % 32
        if pad_w or pad_h:
            padded = cv2.copyMakeBorder(
                image_bgr, 0, pad_h, 0, pad_w, cv2.BORDER_CONSTANT, value=(0, 0, 0)
            )
        else:
            padded = image_bgr
        ph, pw = padded.shape[:2]
        self._detector.setInputSize((pw, ph))
        _retval, faces = self._detector.detect(padded)
        return faces
