from __future__ import annotations

import numpy as np

from clonebins_core.cluster import cluster_embeddings


def test_two_separated_groups():
    a = np.array([[1.0, 0.0, 0.0], [0.98, 0.02, 0.0], [0.97, 0.03, 0.0]], dtype=np.float32)
    b = np.array([[0.0, 1.0, 0.0], [0.02, 0.98, 0.0], [0.03, 0.97, 0.0]], dtype=np.float32)
    x = np.vstack([a, b])
    # L2 normalize
    x = x / np.linalg.norm(x, axis=1, keepdims=True)
    labels = cluster_embeddings(x, threshold=0.5)
    assert len(set(labels[:3])) == 1
    assert len(set(labels[3:])) == 1
    assert labels[0] != labels[3]


def test_single_vector():
    x = np.array([[1.0, 0.0]], dtype=np.float32)
    labels = cluster_embeddings(x, threshold=0.45)
    assert list(labels) == [0]


def test_empty():
    x = np.zeros((0, 4), dtype=np.float32)
    labels = cluster_embeddings(x)
    assert list(labels) == []
