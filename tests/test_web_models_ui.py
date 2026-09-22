"""The Face models management section is gone. Weights ship baked into the app."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "apps/web/src/App.tsx").read_text(encoding="utf-8")
API = (ROOT / "apps/web/src/api.ts").read_text(encoding="utf-8")
STYLES = (ROOT / "apps/web/src/styles.css").read_text(encoding="utf-8")


def test_face_models_management_ui_is_removed() -> None:
    assert "Face models" not in APP
    assert "Open models folder" not in APP
    assert "Copy install command" not in APP
    assert "onVerifyModels" not in APP
    assert "onDownloadModels" not in APP
    assert "startModelVerify" not in APP
    assert "startModelDownload" not in APP
    assert "clonebins models download --force" not in APP
    assert 'className="logbox"' not in APP
    assert ".logbox" not in STYLES
    assert ">Download<" not in APP
    # Zip export stays. Detector/recognizer dropdowns stay in Settings.
    assert "Download zip" in APP
    assert "Face detector (YuNet)" in APP
    assert "Face recognizer (SFace)" in APP
    assert 'step">02' in APP
    assert "Settings" in APP


def test_web_client_does_not_call_model_management_endpoints() -> None:
    for needle in (
        "/api/models/verify",
        "/api/models/download",
        "/api/models/open-folder",
        "/api/models/install-command",
        "startModelVerify",
        "startModelDownload",
        "getInstallCommand",
        "openModelsFolder",
        "getModelStatus",
    ):
        assert needle not in API
