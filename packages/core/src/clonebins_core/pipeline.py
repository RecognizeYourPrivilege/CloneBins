"""End-to-end scan → embed → cluster → (optional) export."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clonebins_core.cluster import DEFAULT_THRESHOLD, cluster_embeddings
from clonebins_core.embed import stack_embeddings
from clonebins_core.embed.factory import HybridEmbedder, build_embedder
from clonebins_core.export import export_plan, subject_name
from clonebins_core.io import load_image_bgr
from clonebins_core.progress import NullProgress, ProgressReporter
from clonebins_core.scan import scan_images
from clonebins_core.types import (
    ClusterBin,
    ClusterMode,
    ClusterPlan,
    ImageRecord,
    Naming,
    Placement,
)


@dataclass
class PipelineConfig:
    input_dir: Path
    output_dir: Path
    mode: ClusterMode = ClusterMode.FACE
    threshold: float = DEFAULT_THRESHOLD
    min_images: int = 2
    dry_run: bool = False
    placement: Placement = Placement.COPY
    naming: Naming = Naming.KEEP
    subject_prefix: str = "subject"
    recursive: bool = True
    download_models: bool = True
    models_dir: Path | None = None
    yunet_id: str = "2023mar"
    sface_id: str = "2021dec"
    embedder: HybridEmbedder | None = None


def run_pipeline(config: PipelineConfig, progress: ProgressReporter | None = None) -> ClusterPlan:
    reporter = progress or NullProgress()
    input_dir = config.input_dir.expanduser().resolve()

    reporter.start("scan")
    paths = scan_images(input_dir, recursive=config.recursive)
    reporter.log(f"Found {len(paths)} image(s) under {input_dir}")
    reporter.finish("scan")

    notes: list[str] = []
    embedder = config.embedder
    if embedder is None:
        embedder, notes = build_embedder(
            config.mode,
            download_models=config.download_models,
            models_dir=config.models_dir,
            log=reporter.log,
            yunet_id=config.yunet_id,
            sface_id=config.sface_id,
        )

    records: list[ImageRecord] = []
    reporter.start("embed", total=len(paths))
    for path in paths:
        rel = _relative_name(path, input_dir)
        record = ImageRecord(path=path, relative_name=rel)
        try:
            image = load_image_bgr(path)
            result = embedder.embed(image)
        except KeyboardInterrupt:
            reporter.log("Cancelled during embedding.")
            raise
        except Exception as exc:  # corrupt-tolerant: skip this file only
            record.skipped = True
            record.skip_reason = str(exc)
            records.append(record)
            reporter.log(f"Skip {rel}: {exc}")
            reporter.advance("embed", message=rel)
            continue

        record.faces_found = result.faces_found
        record.used_face = result.used_face
        record.used_body = result.used_body
        if result.embedding is None:
            record.unmatched = True
            record.unmatched_reason = result.note or "no embedding"
        else:
            record.embedding = result.embedding
        records.append(record)
        reporter.advance("embed", message=rel)
    reporter.finish("embed")

    usable = [r for r in records if r.embedding is not None]
    skipped = [r for r in records if r.skipped]
    unmatched = [r for r in records if r.unmatched]

    reporter.start("cluster")
    plan = _build_plan(
        usable,
        skipped=skipped,
        unmatched=unmatched,
        threshold=config.threshold,
        min_images=config.min_images,
        subject_prefix=config.subject_prefix,
        backend_name=embedder.name,
        notes=notes,
        scanned=len(paths),
    )
    reporter.log(
        f"Clusters: {len(plan.clusters)} exportable, "
        f"{len(plan.dropped)} below min-images={config.min_images}"
    )
    reporter.finish("cluster")

    if config.dry_run:
        reporter.log("Dry run — not writing output folders.")
        return plan

    reporter.start("export", total=plan.exportable_count)
    written = export_plan(
        plan,
        config.output_dir,
        placement=config.placement,
        naming=config.naming,
    )
    reporter.log(f"Wrote {len(written)} file(s) under {config.output_dir}")
    reporter.finish("export")
    return plan


def _build_plan(
    usable: list[ImageRecord],
    *,
    skipped: list[ImageRecord],
    unmatched: list[ImageRecord],
    threshold: float,
    min_images: int,
    subject_prefix: str,
    backend_name: str,
    notes: list[str],
    scanned: int,
) -> ClusterPlan:
    plan = ClusterPlan(
        skipped=skipped,
        unmatched=unmatched,
        scanned=scanned,
        backend_name=backend_name,
        notes=list(notes),
    )
    if not usable:
        return plan

    matrix = stack_embeddings([r.embedding for r in usable if r.embedding is not None])
    labels = cluster_embeddings(matrix, threshold=threshold)

    grouped: dict[int, list[ImageRecord]] = {}
    for record, label in zip(usable, labels, strict=True):
        grouped.setdefault(int(label), []).append(record)

    # Largest clusters first — those are the most useful LoRA bins.
    ordered = sorted(grouped.values(), key=lambda members: (-len(members), members[0].relative_name))
    exportable = [g for g in ordered if len(g) >= min_images]
    dropped_groups = [g for g in ordered if len(g) < min_images]

    for i, members in enumerate(exportable, start=1):
        plan.clusters.append(
            ClusterBin(index=i, name=subject_name(subject_prefix, i, len(exportable)), members=members)
        )
    for i, members in enumerate(dropped_groups, start=1):
        plan.dropped.append(ClusterBin(index=i, name=f"_dropped_{i:02d}", members=members))
    return plan


def _relative_name(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name
