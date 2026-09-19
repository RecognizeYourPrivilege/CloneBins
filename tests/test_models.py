"""Face-model catalog (no network)."""

from clonebins_core.models import (
    DEFAULT_SFACE_ID,
    DEFAULT_YUNET_ID,
    SFACE_MODELS,
    YUNET_MODELS,
    catalog_status,
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
