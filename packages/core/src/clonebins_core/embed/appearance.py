"""Lightweight body/appearance embedding (no extra model download).

This is a ReID-style stand-in: hue-weighted HSV histogram + a light spatial
color grid. It groups images that share palette / clothing / backdrop — useful
for AI-generated character sets, and as the body half of ``face+body``.

Swap this module for CLIP or a dedicated ReID network later without
changing the clustering / export pipeline.
"""

from __future__ import annotations

import cv2
import numpy as np

from clonebins_core.embed import EmbedResult, l2_normalize


class AppearanceEmbedder:
    name = "appearance-hist"

    def __init__(self, size: int = 128, grid: int = 4) -> None:
        self.size = size
        self.grid = grid

    @property
    def embedding_dim(self) -> int:
        return 36 + 16 + 8 + self.grid * self.grid * 3

    def embed_vector(self, image_bgr: np.ndarray) -> np.ndarray:
        img = cv2.resize(image_bgr, (self.size, self.size), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Hue carries identity-ish clothing/hair color; give it most of the mass.
        hist_h = cv2.calcHist([hsv], [0], None, [36], [0, 180]).flatten()
        hist_s = cv2.calcHist([hsv], [1], None, [16], [0, 256]).flatten()
        hist_v = cv2.calcHist([hsv], [2], None, [8], [0, 256]).flatten()
        hist = l2_normalize(
            np.concatenate(
                [
                    l2_normalize(hist_h) * 0.7,
                    l2_normalize(hist_s) * 0.2,
                    l2_normalize(hist_v) * 0.1,
                ]
            )
        )

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        cell_h = self.size // self.grid
        cell_w = self.size // self.grid
        cells: list[np.ndarray] = []
        for row in range(self.grid):
            for col in range(self.grid):
                cell = rgb[row * cell_h : (row + 1) * cell_h, col * cell_w : (col + 1) * cell_w]
                cells.append(cell.mean(axis=(0, 1)))
        spatial = l2_normalize(np.concatenate(cells).astype(np.float32))

        return l2_normalize(np.concatenate([hist * 0.85, spatial * 0.15]))

    def embed(self, image_bgr: np.ndarray) -> EmbedResult:
        return EmbedResult(
            embedding=self.embed_vector(image_bgr),
            faces_found=0,
            used_face=False,
            used_body=True,
        )
