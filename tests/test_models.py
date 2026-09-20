"""Face-model catalog (no network)."""

from clonebins_core.models import (
    DEFAULT_SFACE_ID,
    DEFAULT_YUNET_ID,
    SFACE_MODELS,
    YUNET_MODELS,
    catalog_status,
    download_missing_face_models,
    missing_model_specs,
    resolve_model_paths,
)


def test_three_yunet_and_three_sface_variants(tmp_path):
    assert [m.id for m in YUNET_MODELS] == ["2023mar", "2023mar_int8", "2023mar_int8bq"]
    assert [m.id for m in SFACE_MODELS] == ["2021dec", "2021dec_int8", "2021dec_int8bq"]
    paths = resolve_model_paths(tmp_path, yunet_id="2023mar_int8", sface_id="2021dec_int8bq")
    assert paths.yunet.name.endswith("int8.onnx")
    assert paths.sface.name.endswith("int8bq.onnx")
    assert paths.yunet_id == "2023mar_int8"
    assert paths.sface_id == "2021dec_int8bq"


def test_catalog_status_lists_all_missing(tmp_path):
    catalog = catalog_status(tmp_path)
    assert catalog["default_yunet"] == DEFAULT_YUNET_ID
    assert catalog["default_sface"] == DEFAULT_SFACE_ID
    assert len(catalog["yunet"]) == 3
    assert len(catalog["sface"]) == 3
    assert all(not item["ready"] for item in catalog["yunet"] + catalog["sface"])
    missing = missing_model_specs(tmp_path)
    assert len(missing) == 6


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
    assert len(calls) == 5
    download_missing_face_models(models_dir=tmp_path, all_variants=True)
    assert len(calls) == 5
