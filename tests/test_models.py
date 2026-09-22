"""Face-model catalog and download (mock network unless marked live)."""

from __future__ import annotations

import pytest

from clonebins_core.models import (
    ALL_MODELS,
    CATALOG_SIZE,
    DEFAULT_SFACE_ID,
    DEFAULT_YUNET_ID,
    EXPECTED_FILENAMES,
    INSTALL_COMMAND,
    SFACE_MODELS,
    YUNET_MODELS,
    _download_first_ok,
    catalog_status,
    curl_install_script,
    default_models_dir,
    copy_bundled_into_cache,
    download_all_face_models,
    download_missing_face_models,
    ensure_face_models,
    missing_model_specs,
    resolve_model_paths,
    user_home,
    verify_and_fill_face_models,
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
        assert any("media.githubusercontent.com" in url for url in spec.urls)
        assert any("github.com/opencv/opencv_zoo/raw/" in url for url in spec.urls)
        assert any("jsdelivr.net" in url for url in spec.urls)
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


def test_download_writes_all_seven_filenames(tmp_path, monkeypatch):
    calls: list[str] = []

    def fake_download(urls, dest, min_bytes, log=None):
        calls.append(dest.name)
        dest.write_bytes(b"y" * (min_bytes + 10))

    monkeypatch.setattr("clonebins_core.models._download_first_ok", fake_download)
    root = download_all_face_models(models_dir=tmp_path)
    assert root == tmp_path
    assert calls == list(EXPECTED_FILENAMES)
    assert {p.name for p in tmp_path.glob("*.onnx")} == set(EXPECTED_FILENAMES)
    for spec in ALL_MODELS:
        assert (tmp_path / spec.filename).stat().st_size >= spec.min_bytes


def test_download_missing_skips_present(tmp_path, monkeypatch):
    yunet = tmp_path / "face_detection_yunet_2023mar.onnx"
    yunet.write_bytes(b"x" * 60_000)
    calls: list[str] = []

    def fake_download(urls, dest, min_bytes, log=None):
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


def test_baked_models_fill_cache_before_network(tmp_path, monkeypatch):
    baked = tmp_path / "baked"
    cache = tmp_path / "cache"
    baked.mkdir()
    present = YUNET_MODELS[0]
    (baked / present.filename).write_bytes(b"b" * (present.min_bytes + 8))
    monkeypatch.setenv("CLONEBINS_BUNDLED_MODELS", str(baked))
    calls: list[str] = []

    def fake_download(urls, dest, min_bytes, log=None):
        calls.append(dest.name)
        dest.write_bytes(b"y" * (min_bytes + 10))

    monkeypatch.setattr("clonebins_core.models._download_first_ok", fake_download)
    copied = copy_bundled_into_cache(cache)
    assert copied == [present.filename]
    root = verify_and_fill_face_models(models_dir=cache)
    assert root == cache
    assert present.filename not in calls
    assert len(calls) == 6
    assert (cache / present.filename).stat().st_size >= present.min_bytes

    def boom(*_args, **_kwargs):
        raise AssertionError("baked defaults must not hit the network")

    monkeypatch.setattr("clonebins_core.models._download_first_ok", boom)
    paths = ensure_face_models(
        models_dir=cache,
        download=True,
        yunet_id=present.id,
        sface_id=SFACE_MODELS[0].id,
    )
    # SFace was filled by verify_and_fill above, YuNet came from the bundle.
    assert paths.yunet.is_file()
    assert paths.sface.is_file()


def test_download_force_refetches_present(tmp_path, monkeypatch):
    for spec in ALL_MODELS:
        (tmp_path / spec.filename).write_bytes(b"x" * (spec.min_bytes + 8))
    calls: list[str] = []

    def fake_download(urls, dest, min_bytes, log=None):
        calls.append(dest.name)
        dest.write_bytes(b"z" * (min_bytes + 10))

    monkeypatch.setattr("clonebins_core.models._download_first_ok", fake_download)
    download_missing_face_models(models_dir=tmp_path, all_variants=True, force=True)
    assert calls == list(EXPECTED_FILENAMES)


def test_download_falls_back_to_curl_when_urllib_fails(tmp_path, monkeypatch):
    dest = tmp_path / "face_detection_yunet_2023mar.onnx"
    urls = ALL_MODELS[0].urls[:1]

    def boom(url, dest_path, timeout=180):
        raise OSError("CERTIFICATE_VERIFY_FAILED")

    def fake_curl(url, dest_path, timeout=180):
        dest_path.write_bytes(b"onnx-bytes" * 8000)

    monkeypatch.setattr("clonebins_core.models._download_url", boom)
    monkeypatch.setattr("clonebins_core.models._download_url_curl", fake_curl)
    _download_first_ok(urls, dest, min_bytes=50_000)
    assert dest.is_file()
    assert dest.stat().st_size >= 50_000


def test_install_command_and_curl_script(tmp_path):
    assert INSTALL_COMMAND == "clonebins models download --force"
    script = curl_install_script(tmp_path)
    assert "mkdir -p" in script
    for name in EXPECTED_FILENAMES:
        assert name in script
    assert "media.githubusercontent.com" in script or "huggingface.co" in script


def test_live_smoke_downloads_one_yunet(tmp_path):
    spec = YUNET_MODELS[0]
    dest = tmp_path / spec.filename
    try:
        _download_first_ok(spec.urls, dest, min_bytes=spec.min_bytes)
    except Exception as exc:
        pytest.skip(f"live download unavailable: {exc}")
    assert dest.is_file()
    assert dest.stat().st_size >= spec.min_bytes
    assert dest.read_bytes()[:1] not in {b"<", b"{", b"#"}


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
