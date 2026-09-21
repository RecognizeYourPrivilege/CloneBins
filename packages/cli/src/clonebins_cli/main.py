"""Typer CLI wrapping clonebins_core."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn
from rich.table import Table

from clonebins_core.cluster import DEFAULT_THRESHOLD
from clonebins_core.models import (
    DEFAULT_SFACE_ID,
    DEFAULT_YUNET_ID,
    INSTALL_COMMAND,
    SFACE_BY_ID,
    YUNET_BY_ID,
    catalog_status,
    default_models_dir,
    download_missing_face_models,
    ensure_face_models,
    models_present,
)
from clonebins_core.pipeline import PipelineConfig, run_pipeline
from clonebins_core.types import ClusterMode, ClusterPlan, Naming, Placement

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Cluster AI-generated images by face/body identity into LoRA dataset folders.",
)
models_app = typer.Typer(help="Download and inspect local face models.")
app.add_typer(models_app, name="models")

console = Console()
err_console = Console(stderr=True)


class ModeChoice(str, Enum):
    face = "face"
    face_body = "face+body"


class RichProgress:
    def __init__(self) -> None:
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}[/bold]"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total} {task.fields[detail]}"),
            console=err_console,
            transient=True,
        )
        self._tasks: dict[str, TaskID] = {}
        self._started = False

    def __enter__(self) -> "RichProgress":
        self._progress.start()
        self._started = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._started:
            self._progress.stop()

    def log(self, message: str) -> None:
        err_console.print(message)

    def start(self, phase: str, total: int | None = None) -> None:
        labels = {
            "scan": "Scanning",
            "embed": "Detect / embed",
            "cluster": "Clustering",
            "export": "Exporting",
        }
        desc = labels.get(phase, phase)
        task_total = total if total and total > 0 else None
        self._tasks[phase] = self._progress.add_task(desc, total=task_total or 1, detail="")

    def advance(self, phase: str, step: int = 1, message: str = "") -> None:
        task_id = self._tasks.get(phase)
        if task_id is None:
            return
        self._progress.update(task_id, advance=step, detail=message)

    def finish(self, phase: str) -> None:
        task_id = self._tasks.get(phase)
        if task_id is None:
            return
        self._progress.update(task_id, detail="done")


def _parse_mode(value: str) -> ClusterMode:
    normalized = value.lower().strip().replace(" ", "")
    if normalized in {"face", "face-only", "face_only"}:
        return ClusterMode.FACE
    if normalized in {"face+body", "face-body", "face_body", "body"}:
        return ClusterMode.FACE_BODY
    raise typer.BadParameter("Use --mode face or --mode face+body")


@app.callback()
def _root() -> None:
    """CloneBins — local identity bins for LoRA training sets."""


@app.command()
def version() -> None:
    """Print the CLI version."""
    from importlib.metadata import PackageNotFoundError, version as pkg_version

    try:
        console.print(pkg_version("clonebins"))
    except PackageNotFoundError:
        console.print("0.1.3")


@app.command()
def cluster(
    input_dir: Annotated[
        Path,
        typer.Option("--input", "-i", exists=True, file_okay=False, dir_okay=True, readable=True),
    ],
    output_dir: Annotated[Path, typer.Option("--output", "-o", file_okay=False, dir_okay=True)],
    threshold: Annotated[
        float,
        typer.Option(
            "--threshold",
            "-t",
            help="Cosine similarity merge threshold (higher = stricter). Default 0.45.",
        ),
    ] = DEFAULT_THRESHOLD,
    min_images: Annotated[
        int,
        typer.Option("--min-images", help="Drop clusters smaller than this (not exported)."),
    ] = 2,
    mode: Annotated[
        str,
        typer.Option("--mode", help="face (identity from faces) or face+body (faces + appearance)."),
    ] = ModeChoice.face.value,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print the cluster plan without writing files."),
    ] = False,
    copy: Annotated[
        bool,
        typer.Option("--copy/--hardlink", help="Copy files (default) or hardlink into output bins."),
    ] = True,
    keep_names: Annotated[
        bool,
        typer.Option(
            "--keep-names/--rename-index",
            help="Keep original filenames (default) or rename 00001.ext, 00002.ext, …",
        ),
    ] = True,
    subject_prefix: Annotated[
        str,
        typer.Option("--subject-prefix", help="Folder prefix: subject → subject_01, subject_02, …"),
    ] = "subject",
    no_download: Annotated[
        bool,
        typer.Option("--no-download", help="Do not download face models if they are missing."),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option("--recursive/--no-recursive", help="Scan input subfolders (default: on)."),
    ] = True,
    yunet: Annotated[
        str,
        typer.Option(
            "--yunet",
            help="YuNet detector: 2023mar | 2023mar_int8 | 2023mar_int8bq | 2026may.",
        ),
    ] = DEFAULT_YUNET_ID,
    sface: Annotated[
        str,
        typer.Option("--sface", help="SFace recognizer: 2021dec | 2021dec_int8 | 2021dec_int8bq."),
    ] = DEFAULT_SFACE_ID,
) -> None:
    """Scan an image folder, cluster identities, and write output/<subject>/ bins."""
    cluster_mode = _parse_mode(mode)
    if min_images < 1:
        raise typer.BadParameter("--min-images must be >= 1")
    if not 0.0 <= threshold <= 1.0:
        raise typer.BadParameter("--threshold must be between 0 and 1 (cosine similarity)")

    if yunet not in YUNET_BY_ID:
        raise typer.BadParameter(f"--yunet must be one of: {', '.join(YUNET_BY_ID)}")
    if sface not in SFACE_BY_ID:
        raise typer.BadParameter(f"--sface must be one of: {', '.join(SFACE_BY_ID)}")

    config = PipelineConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        mode=cluster_mode,
        threshold=threshold,
        min_images=min_images,
        dry_run=dry_run,
        placement=Placement.COPY if copy else Placement.HARDLINK,
        naming=Naming.KEEP if keep_names else Naming.INDEX,
        subject_prefix=subject_prefix,
        recursive=recursive,
        download_models=not no_download,
        yunet_id=yunet,
        sface_id=sface,
    )

    try:
        with RichProgress() as progress:
            plan = run_pipeline(config, progress=progress)
    except KeyboardInterrupt:
        err_console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(code=130) from None
    except FileNotFoundError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    _print_plan(plan, config)
    if not plan.clusters and not dry_run:
        raise typer.Exit(code=1)


def _print_plan(plan: ClusterPlan, config: PipelineConfig) -> None:
    for note in plan.notes:
        err_console.print(f"[yellow]{note}[/yellow]")

    table = Table(title="CloneBins cluster plan", show_lines=False)
    table.add_column("Bin", style="cyan")
    table.add_column("Images", justify="right")
    table.add_column("Samples")

    for cluster in plan.clusters:
        table.add_row(cluster.name, str(cluster.size), ", ".join(cluster.sample_names(4)))
    if not plan.clusters:
        table.add_row("—", "0", "no exportable clusters")

    console.print(table)
    console.print(
        f"Backend: {plan.backend_name or 'n/a'}  |  mode={config.mode.value}  |  "
        f"threshold={config.threshold}  |  min-images={config.min_images}"
    )
    console.print(
        f"Scanned {plan.scanned} file(s): "
        f"{plan.exportable_count} exportable, "
        f"{sum(c.size for c in plan.dropped)} dropped, "
        f"{len(plan.unmatched)} unmatched, "
        f"{len(plan.skipped)} skipped"
    )
    if config.dry_run:
        console.print("[yellow]Dry run: no files were written.[/yellow]")
    else:
        console.print(f"Output: {config.output_dir}")


@models_app.command("path")
def models_path() -> None:
    """Print the local models directory."""
    console.print(str(default_models_dir()))


@models_app.command("status")
def models_status() -> None:
    """Check whether YuNet + SFace weights are present locally."""
    directory = default_models_dir()
    catalog = catalog_status(directory)
    console.print(f"{directory}")
    console.print(
        f"Expected {catalog['expected']} ONNX files "
        f"({catalog['yunet_count']} YuNet + {catalog['sface_count']} SFace)"
    )
    for family in ("yunet", "sface"):
        for spec in catalog[family]:
            mark = "ready" if spec["ready"] else "missing"
            console.print(f"  {family} {spec['id']}: {mark}  {spec['filename']}")
    raise typer.Exit(code=0 if models_present(directory) else 1)


@models_app.command("verify")
def models_verify() -> None:
    """Alias for ``status`` — list present vs missing YuNet / SFace files."""
    models_status()


@models_app.command("download")
def models_download(
    models_dir: Annotated[
        Optional[Path],
        typer.Option("--dir", help="Override CLONEBINS_MODELS_DIR."),
    ] = None,
    all_variants: Annotated[
        bool,
        typer.Option(
            "--all/--defaults-only",
            help="Download every YuNet and SFace ONNX variant (default: all seven).",
        ),
    ] = True,
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-download files even if they already look valid."),
    ] = False,
    yunet: Annotated[str, typer.Option("--yunet")] = DEFAULT_YUNET_ID,
    sface: Annotated[str, typer.Option("--sface")] = DEFAULT_SFACE_ID,
) -> None:
    """Download all seven YuNet + SFace ONNX weights into ~/.cache/clonebins/models.

    Already-valid files are skipped unless ``--force``. This is the Terminal
    fallback when the desktop Download button cannot reach the network:

        clonebins models download --force
    """
    try:
        root = download_missing_face_models(
            models_dir=models_dir,
            log=err_console.print,
            all_variants=all_variants,
            force=force,
            yunet_id=yunet,
            sface_id=sface,
        )
        if not all_variants:
            paths = ensure_face_models(
                models_dir=models_dir,
                download=False,
                yunet_id=yunet,
                sface_id=sface,
            )
            console.print(f"YuNet: {paths.yunet}")
            console.print(f"SFace: {paths.sface}")
            return
    except Exception as exc:
        err_console.print(f"[red]{exc}[/red]")
        err_console.print(f"Fallback: {INSTALL_COMMAND}")
        raise typer.Exit(code=1) from exc
    console.print(f"All variants in {root}")
