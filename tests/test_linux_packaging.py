"""Smoke-test Linux packagers with dummy binaries (no Tauri / PyInstaller)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "apps/desktop/scripts/package-linux.sh"


def _dummy_bin(path: Path) -> None:
    path.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    path.chmod(0o755)


def _run(args: list[str], env: dict[str, str] | None = None) -> None:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    subprocess.run(args, check=True, cwd=ROOT, env=merged)


def test_package_linux_deb_and_arch(tmp_path: Path) -> None:
    desktop = tmp_path / "clonebins-desktop"
    api = tmp_path / "clonebins-api"
    _dummy_bin(desktop)
    _dummy_bin(api)

    deb = tmp_path / "CloneBins-0.1.0-ubuntu-amd64.deb"
    arch = tmp_path / "CloneBins-0.1.0-archlinux-x86_64.pkg.tar.zst"

    _run(
        [
            "bash",
            str(SCRIPT),
            "deb",
            "--desktop",
            str(desktop),
            "--api",
            str(api),
            "--out",
            str(deb),
        ]
    )
    assert deb.is_file() and deb.stat().st_size > 0
    listing = subprocess.check_output(["dpkg-deb", "-c", str(deb)], text=True)
    assert "usr/bin/clonebins-desktop" in listing
    assert "usr/bin/clonebins-api" in listing
    assert "usr/share/applications/clonebins.desktop" in listing
    control = subprocess.check_output(["dpkg-deb", "-f", str(deb), "Package"], text=True)
    assert control.strip() == "clonebins"

    _run(
        [
            "bash",
            str(SCRIPT),
            "arch",
            "--desktop",
            str(desktop),
            "--api",
            str(api),
            "--out",
            str(arch),
        ]
    )
    assert arch.is_file() and arch.stat().st_size > 0
    arch_list = subprocess.check_output(["tar", "-tf", str(arch)], text=True)
    assert "usr/bin/clonebins-desktop" in arch_list
    assert "usr/bin/clonebins-api" in arch_list
    assert ".PKGINFO" in arch_list
