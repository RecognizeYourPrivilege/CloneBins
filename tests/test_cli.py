from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from clonebins_cli.main import app
from portraits import write_identity_set

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "cluster" in result.stdout


def test_cluster_help():
    result = runner.invoke(app, ["cluster", "--help"])
    assert result.exit_code == 0
    assert "--threshold" in result.stdout
    assert "--min-images" in result.stdout
    assert "--mode" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--hardlink" in result.stdout
    assert "--rename-index" in result.stdout
    assert "--subject-prefix" in result.stdout


def test_cluster_end_to_end(tmp_path: Path):
    src = tmp_path / "images"
    write_identity_set(src)
    out = tmp_path / "bins"
    result = runner.invoke(
        app,
        [
            "cluster",
            "--input",
            str(src),
            "--output",
            str(out),
            "--mode",
            "face+body",
            "--no-download",
            "--min-images",
            "2",
            "--threshold",
            "0.5",
            "--subject-prefix",
            "char",
            "--rename-index",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    bins = sorted(p.name for p in out.iterdir() if p.is_dir())
    assert bins == ["char_01", "char_02"]
    for folder in bins:
        files = list((out / folder).glob("*.png"))
        assert len(files) == 3
        assert all(f.name.startswith("000") for f in files)


def test_dry_run_cli(tmp_path: Path):
    src = tmp_path / "images"
    write_identity_set(src)
    out = tmp_path / "bins"
    result = runner.invoke(
        app,
        [
            "cluster",
            "--input",
            str(src),
            "--output",
            str(out),
            "--mode",
            "face+body",
            "--no-download",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Dry run" in result.stdout
    assert not out.exists()
