"""Agglomerative clustering on cosine similarity."""

from __future__ import annotations

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_distances

# Default cosine similarity; SFace same-person scores are often ~0.36+.
# Higher = stricter (fewer merges). Documented in README / CLI help.
DEFAULT_THRESHOLD = 0.45


def cluster_embeddings(
    embeddings: np.ndarray,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> np.ndarray:
    """Return integer labels for each row.

    ``threshold`` is cosine *similarity*. It is converted to cosine distance
    ``1 - threshold`` for average-linkage agglomerative clustering.
    """
    if embeddings.ndim != 2:
        raise ValueError("embeddings must be a 2D array")
    n = embeddings.shape[0]
    if n == 0:
        return np.array([], dtype=int)
    if n == 1:
        return np.array([0], dtype=int)

    distance_threshold = max(0.0, min(2.0, 1.0 - float(threshold)))
    # Precomputed cosine distances are compatible across sklearn versions
    # that use either `metric=` or the older `affinity=` argument.
    distances = cosine_distances(embeddings)
    np.fill_diagonal(distances, 0.0)
    distances = np.clip(distances, 0.0, 2.0)
    labels = _fit_agglomerative(distances, distance_threshold)
    return np.asarray(labels, dtype=int)


def _fit_agglomerative(distances: np.ndarray, distance_threshold: float) -> np.ndarray:
    common = dict(
        n_clusters=None,
        linkage="average",
        distance_threshold=distance_threshold,
    )
    try:
        model = AgglomerativeClustering(metric="precomputed", **common)
    except TypeError:
        model = AgglomerativeClustering(affinity="precomputed", **common)
    return model.fit_predict(distances)
