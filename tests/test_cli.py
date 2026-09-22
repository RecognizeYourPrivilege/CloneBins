from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from clonebins_cli.main import app
from conftest import visible_help
from portraits import write_identity_set

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "cluster" in visible_help(result.stdout)


def test_models_status_and_verify(tmp_path, monkeypatch):
    monkeypatch.setenv("CLONEBINS_MODELS_DIR", str(tmp_path))
    status = runner.invoke(app, ["models", "status"])
    assert "missing" in status.stdout
    help_models = runner.invoke(app, ["models", "--help"])
    text = visible_help(help_models.stdout)
    assert "status" in text
    assert "download" in text
    assert "verify" in text
    download_help = runner.invoke(app, ["models", "download", "--help"])
    assert download_help.exit_code == 0
    help_text = visible_help(download_help.stdout)
    assert "--force" in help_text
    assert "--all" in help_text
    calls: list[str] = []

    def fake_download(urls, dest, min_bytes, log=None):
        calls.append(dest.name)
        dest.write_bytes(b"x" * (min_bytes + 8))

    monkeypatch.setattr("clonebins_core.models._download_first_ok", fake_download)
    verify = runner.invoke(app, ["models", "verify"])
    assert verify.exit_code == 0, verify.stdout + verify.stderr
    output = verify.stdout + verify.stderr
    assert "2026may" in output
    assert "yunet" in output.lower() or "face_detection_yunet" in output
    assert len(calls) == 7
    assert all((tmp_path / name).is_file() for name in calls)
    again = runner.invoke(app, ["models", "verify"])
    assert again.exit_code == 0
    assert len(calls) == 7


def test_cli_download_force_writes_all_seven(tmp_path, monkeypatch):
    monkeypatch.setenv("CLONEBINS_MODELS_DIR", str(tmp_path))
    calls: list[str] = []

    def fake_download(urls, dest, min_bytes, log=None):
        calls.append(dest.name)
        dest.write_bytes(b"x" * (min_bytes + 8))

    monkeypatch.setattr("clonebins_core.models._download_first_ok", fake_download)
    result = runner.invoke(app, ["models", "download", "--force"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert calls == [
        "face_detection_yunet_2023mar.onnx",
        "face_detection_yunet_2023mar_int8.onnx",
        "face_detection_yunet_2023mar_int8bq.onnx",
        "face_detection_yunet_2026may.onnx",
        "face_recognition_sface_2021dec.onnx",
        "face_recognition_sface_2021dec_int8.onnx",
        "face_recognition_sface_2021dec_int8bq.onnx",
    ]
    assert all((tmp_path / name).is_file() for name in calls)


def test_cluster_help():
    result = runner.invoke(app, ["cluster", "--help"])
    assert result.exit_code == 0
    text = visible_help(result.stdout)
    assert "--threshold" in text
    assert "--min-images" in text
    assert "--mode" in text
    assert "--dry-run" in text
    assert "--hardlink" in text
    assert "--rename-index" in text
    assert "--subject-prefix" in text
    assert "--yunet" in text
    assert "--sface" in text


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
