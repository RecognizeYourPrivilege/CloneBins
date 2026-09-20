"""Guard the macOS DMG release workflow and packaging scripts (no Tauri)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/release-macos.yml"
FREEZE = ROOT / "apps/desktop/scripts/freeze-python-bin.sh"
PACKAGE = ROOT / "apps/desktop/scripts/package-macos-dmg.sh"
DESKTOP_README = ROOT / "apps/desktop/README.md"


def test_macos_release_uses_native_intel_runner() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "macos-15-intel" in text
    assert "macos-latest" in text
    # Rosetta-cross on Apple Silicon leaked arm64 cryptography on v0.1.1.
    # Comments may mention the old command; the job steps must not run it.
    assert 'arch -x86_64 "$PYTHON"' not in text
    assert "arch -x86_64 /usr/bin/true" not in text
    assert "cancel-in-progress: false" in text
    assert "release-macos-${{ github.ref }}" in text
    assert "CloneBins-${VERSION}-macos-${{ matrix.arch }}.dmg" in text
    assert "APPLE_CERTIFICATE" in text
    assert "APPLE_API_KEY" in text
    pkg = PACKAGE.read_text(encoding="utf-8")
    assert "README-UNSIGNED" in pkg
    # macos-15-intel undersized -srcfolder images; we allocate explicitly.
    assert "hdiutil convert" in pkg
    assert "SIZE_MB" in pkg
    assert "hdiutil create" in pkg
    assert all(
        "-srcfolder" not in line or line.lstrip().startswith("#")
        for line in pkg.splitlines()
    )


def test_freeze_script_collects_share_deps() -> None:
    text = FREEZE.read_text(encoding="utf-8")
    for flag in (
        "--hidden-import paramiko",
        "--hidden-import smbclient",
        "--hidden-import smbprotocol",
        "--hidden-import clonebins_api.shares",
        "--collect-all paramiko",
        "--collect-all smbprotocol",
        "--collect-all certifi",
        "--hidden-import certifi",
        "--target-arch",
    ):
        assert flag in text


def test_desktop_readme_documents_apple_secrets() -> None:
    text = DESKTOP_README.read_text(encoding="utf-8")
    assert "APPLE_CERTIFICATE" in text
    assert "APPLE_ID" in text
    assert "APPLE_API_KEY" in text
    assert "macos-15-intel" in text
    assert "unsigned" in text.lower()


def test_sidecar_pins_models_dir_to_user_home() -> None:
    rust = (ROOT / "apps/desktop/src-tauri/src/lib.rs").read_text(encoding="utf-8")
    assert "fn apply_user_cache_env" in rust
    assert 'cmd.env("HOME"' in rust
    assert 'cmd.env(\n            "CLONEBINS_MODELS_DIR"' in rust or "CLONEBINS_MODELS_DIR" in rust
    assert 'home.join(".cache").join("clonebins").join("models")' in rust
