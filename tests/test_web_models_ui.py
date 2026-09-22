"""Guard the web/desktop Face models controls (no browser)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "apps/web/src/App.tsx").read_text(encoding="utf-8")
API = (ROOT / "apps/web/src/api.ts").read_text(encoding="utf-8")


def test_download_button_is_not_gated_on_verify() -> None:
    assert "Download missing" not in APP
    assert ">Download<" in APP or ">\n              Download\n            </button>" in APP
    assert "const downloadEnabled = !downloadingModels;" in APP
    assert "if (modelMissing === null || modelMissing <= 0) return;" not in APP
    assert "clonebins models download --force" in APP
    assert "Open models folder" in APP
    assert "Copy install command" in APP
    assert "Download is always enabled" in APP


def test_download_api_always_sends_all_variants() -> None:
    assert "all_variants: true" in API
    assert "Boolean(options.force)" in API
    assert "/api/models/open-folder" in API
    assert "/api/models/install-command" in API
    assert "/api/models/verify" in API
    assert "startModelVerify" in API
    assert "copying baked models" in APP
    assert "downloads only missing" in APP
