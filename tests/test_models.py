"""Face-model catalog (no network)."""

from clonebins_core.models import (
    ALL_MODELS,
    CATALOG_SIZE,
    DEFAULT_SFACE_ID,
    DEFAULT_YUNET_ID,
    SFACE_MODELS,
    YUNET_MODELS,
    catalog_status,
    default_models_dir,
    download_missing_face_models,
    missing_model_specs,
    resolve_model_paths,
    user_home,
)


def test_four_yunet_and_three_sface_variants(tmp_path):
    assert [m.id for m in YUNET_MODELS] == ["2023mar", "2023mar_int8", "2023mar_int8bq", "2026may"]
    assert [m.id for m in SFACE_MODELS] == ["2021dec", "2021dec_int8", "2021dec_int8bq"]
    assert len(ALL_MODELS) == CATALOG_SIZE == 7
    assert [m.filename for m in YUNET_MODELS] == [
        "face_detection_yunet_2023mar.onnx",
        "face_detection_yunet_2023mar_int8.onnx",
        "face_detection_yunet_2023mar_int8bq.onnx",
        "face_detection_yunet_2026may.onnx",
    ]
    assert [m.filename for m in SFACE_MODELS] == [
        "face_recognition_sface_2021dec.onnx",
        "face_recognition_sface_2021dec_int8.onnx",
        "face_recognition_sface_2021dec_int8bq.onnx",
    ]
    paths = resolve_model_paths(tmp_path, yunet_id="2023mar_int8", sface_id="2021dec_int8bq")
    assert paths.yunet.name.endswith("int8.onnx")
    assert paths.sface.name.endswith("int8bq.onnx")
    assert paths.yunet_id == "2023mar_int8"
    assert paths.sface_id == "2021dec_int8bq"


def test_catalog_lists_huggingface_urls():
    for spec in ALL_MODELS:
        assert spec.urls[0].startswith("https://huggingface.co/opencv/")
        assert spec.filename in spec.urls[0]
        assert any("huggingface.co" in url for url in spec.urls)
        assert any("opencv_zoo" in url for url in spec.urls)


def test_catalog_status_lists_all_missing(tmp_path):
    catalog = catalog_status(tmp_path)
    assert catalog["default_yunet"] == DEFAULT_YUNET_ID
    assert catalog["default_sface"] == DEFAULT_SFACE_ID
    assert catalog["expected"] == 7
    assert catalog["yunet_count"] == 4
    assert catalog["sface_count"] == 3
    assert catalog["all_ready"] is False
    assert len(catalog["yunet"]) == 4
    assert len(catalog["sface"]) == 3
    assert all(not item["ready"] for item in catalog["yunet"] + catalog["sface"])
    assert all(item["path"].startswith(str(tmp_path)) for item in catalog["yunet"] + catalog["sface"])
    missing = missing_model_specs(tmp_path)
    assert len(missing) == 7
    assert {item["filename"] for item in missing} == {spec.filename for spec in ALL_MODELS}


def test_download_missing_skips_present(tmp_path, monkeypatch):
    yunet = tmp_path / "face_detection_yunet_2023mar.onnx"
    yunet.write_bytes(b"x" * 60_000)
    calls: list[str] = []

    def fake_download(urls, dest, min_bytes):
        calls.append(dest.name)
        dest.write_bytes(b"y" * (min_bytes + 10))

    monkeypatch.setattr("clonebins_core.models._download_first_ok", fake_download)
    download_missing_face_models(models_dir=tmp_path, all_variants=True)
    assert yunet.name not in calls
    assert "face_recognition_sface_2021dec.onnx" in calls
    assert "face_detection_yunet_2026may.onnx" in calls
    assert len(calls) == 6
    download_missing_face_models(models_dir=tmp_path, all_variants=True)
    assert len(calls) == 6


def test_default_models_dir_uses_home_cache(monkeypatch, tmp_path):
    monkeypatch.delenv("CLONEBINS_MODELS_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("USERPROFILE", raising=False)
    assert user_home() == tmp_path
    assert default_models_dir() == (tmp_path / ".cache" / "clonebins" / "models").resolve()


def test_models_dir_expands_tilde_override(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLONEBINS_MODELS_DIR", "~/.cache/clonebins/models")
    assert default_models_dir() == (tmp_path / ".cache" / "clonebins" / "models").resolve()


def test_empty_or_tilde_home_does_not_leave_unexpanded(monkeypatch, tmp_path):
    monkeypatch.delenv("CLONEBINS_MODELS_DIR", raising=False)
    monkeypatch.setenv("HOME", "")
    monkeypatch.delenv("USERPROFILE", raising=False)
    path = default_models_dir()
    assert path.is_absolute()
    assert "~" not in path.parts
    assert path.parts[-3:] == (".cache", "clonebins", "models")

    monkeypatch.setenv("HOME", "~")
    path = default_models_dir()
    assert path.is_absolute()
    assert "~" not in path.parts


def test_user_home_ignores_relative_home(monkeypatch):
    monkeypatch.delenv("CLONEBINS_MODELS_DIR", raising=False)
    monkeypatch.setenv("HOME", "not-a-real-home")
    home = user_home()
    assert home.is_absolute()
    assert home.name != "not-a-real-home"
