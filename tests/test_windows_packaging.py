"""Smoke-test the Windows zip packager with dummy binaries (no Tauri / PyInstaller)."""

from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "apps/desktop/scripts/package-windows.sh"


def _run(args: list[str]) -> None:
    subprocess.run(args, check=True, cwd=ROOT, env=os.environ.copy())


def test_package_windows_zip_and_nsis(tmp_path: Path) -> None:
    desktop = tmp_path / "CloneBins.exe"
    api = tmp_path / "clonebins-api.exe"
    loader = tmp_path / "WebView2Loader.dll"
    installer = tmp_path / "CloneBins_0.1.1_x64-setup.exe"
    desktop.write_bytes(b"MZ-desktop")
    api.write_bytes(b"MZ-api")
    loader.write_bytes(b"MZ-webview")
    installer.write_bytes(b"MZ-nsis")

    out_zip = tmp_path / "CloneBins-0.1.1-windows-x64.zip"
    _run(
        [
            "bash",
            str(SCRIPT),
            "zip",
            "--desktop",
            str(desktop),
            "--api",
            str(api),
            "--extra",
            str(loader),
            "--out",
            str(out_zip),
        ]
    )
    assert out_zip.is_file() and out_zip.stat().st_size > 0
    with zipfile.ZipFile(out_zip) as zf:
        names = set(zf.namelist())
        assert "CloneBins/CloneBins.exe" in names
        assert "CloneBins/clonebins-api.exe" in names
        assert "CloneBins/WebView2Loader.dll" in names
        assert zf.read("CloneBins/CloneBins.exe") == b"MZ-desktop"
        assert zf.read("CloneBins/clonebins-api.exe") == b"MZ-api"

    out_setup = tmp_path / "CloneBins-0.1.1-windows-x64-setup.exe"
    _run(
        [
            "bash",
            str(SCRIPT),
            "nsis",
            "--installer",
            str(installer),
            "--out",
            str(out_setup),
        ]
    )
    assert out_setup.read_bytes() == b"MZ-nsis"
