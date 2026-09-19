from __future__ import annotations

from pathlib import Path

from clonebins_core.embed.appearance import AppearanceEmbedder
from clonebins_core.embed.factory import HybridEmbedder
from clonebins_core.pipeline import PipelineConfig, run_pipeline
from clonebins_core.types import ClusterMode, Naming, Placement
from portraits import write_identity_set


def _appearance_only() -> HybridEmbedder:
    return HybridEmbedder(mode=ClusterMode.FACE_BODY, face=None, body=AppearanceEmbedder())


def test_pipeline_clusters_two_identities(tmp_path: Path):
    src = tmp_path / "in"
    write_identity_set(src)
    (src / "broken.jpg").write_text("this is not an image")
    out = tmp_path / "out"

    plan = run_pipeline(
        PipelineConfig(
            input_dir=src,
            output_dir=out,
            mode=ClusterMode.FACE_BODY,
            threshold=0.5,
            min_images=2,
            dry_run=False,
            placement=Placement.COPY,
            naming=Naming.KEEP,
            subject_prefix="subject",
            download_models=False,
            embedder=_appearance_only(),
        )
    )

    assert plan.scanned == 7  # 6 portraits + corrupt
    assert len(plan.skipped) == 1
    assert len(plan.clusters) == 2
    sizes = sorted(c.size for c in plan.clusters)
    assert sizes == [3, 3]

    names = {p.name for p in (out / "subject_01").iterdir()} | {p.name for p in (out / "subject_02").iterdir()}
    assert "red_01.png" in names
    assert "blue_01.png" in names
    # corrupt file must not be exported
    assert "broken.jpg" not in names

    # each bin is a single identity
    for cluster in plan.clusters:
        prefixes = {m.path.name.split("_")[0] for m in cluster.members}
        assert len(prefixes) == 1


def test_dry_run_writes_nothing(tmp_path: Path):
    src = tmp_path / "in"
    write_identity_set(src)
    out = tmp_path / "out"
    plan = run_pipeline(
        PipelineConfig(
            input_dir=src,
            output_dir=out,
            mode=ClusterMode.FACE_BODY,
            min_images=2,
            dry_run=True,
            download_models=False,
            embedder=_appearance_only(),
        )
    )
    assert plan.clusters
    assert not out.exists()


def test_min_images_drops_small_bins(tmp_path: Path):
    src = tmp_path / "in"
    write_identity_set(src)
    out = tmp_path / "out"
    plan = run_pipeline(
        PipelineConfig(
            input_dir=src,
            output_dir=out,
            mode=ClusterMode.FACE_BODY,
            min_images=10,
            download_models=False,
            embedder=_appearance_only(),
        )
    )
    assert plan.clusters == []
    assert plan.dropped
    assert not any(out.glob("subject_*")) if out.exists() else True
