"""Public types for the CloneBins clustering pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np


class ClusterMode(str, Enum):
    FACE = "face"
    FACE_BODY = "face+body"


class Placement(str, Enum):
    COPY = "copy"
    HARDLINK = "hardlink"


class Naming(str, Enum):
    KEEP = "keep-names"
    INDEX = "rename-index"


@dataclass
class FaceDetection:
    """One detected face in an image (largest is used for embedding)."""

    x: float
    y: float
    width: float
    height: float
    score: float


@dataclass
class ImageRecord:
    path: Path
    relative_name: str
    embedding: np.ndarray | None = None
    face_embedding: np.ndarray | None = None
    body_embedding: np.ndarray | None = None
    faces_found: int = 0
    used_face: bool = False
    used_body: bool = False
    skipped: bool = False
    skip_reason: str | None = None
    unmatched: bool = False
    unmatched_reason: str | None = None


@dataclass
class ClusterBin:
    index: int
    name: str
    members: list[ImageRecord] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.members)

    def sample_names(self, limit: int = 3) -> list[str]:
        return [m.relative_name for m in self.members[:limit]]


@dataclass
class ClusterPlan:
    """Full clustering result, including bins that will not be exported."""

    clusters: list[ClusterBin] = field(default_factory=list)
    dropped: list[ClusterBin] = field(default_factory=list)
    unmatched: list[ImageRecord] = field(default_factory=list)
    skipped: list[ImageRecord] = field(default_factory=list)
    scanned: int = 0
    backend_name: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def exportable_count(self) -> int:
        return sum(c.size for c in self.clusters)

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        for cluster in self.clusters:
            samples = ", ".join(cluster.sample_names())
            extra = f"  e.g. {samples}" if samples else ""
            lines.append(f"  {cluster.name}: {cluster.size} image(s){extra}")
        if self.dropped:
            dropped_n = sum(c.size for c in self.dropped)
            lines.append(
                f"  (dropped {len(self.dropped)} cluster(s) / {dropped_n} image(s) below min-images)"
            )
        if self.unmatched:
            lines.append(f"  unmatched: {len(self.unmatched)} image(s) (no usable embedding)")
        if self.skipped:
            lines.append(f"  skipped: {len(self.skipped)} unreadable/corrupt file(s)")
        return lines
