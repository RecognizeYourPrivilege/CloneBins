from __future__ import annotations

from pathlib import Path

import pytest

from clonebins_api.shares import ShareError, ShareSpec, fetch_share, probe_share, redact


def test_share_spec_redacts_secrets_and_location():
    spec = ShareSpec(
        protocol="sftp",
        host="nas.local",
        path="/gens",
        username="alice",
        password="super-secret",
        private_key="BEGIN KEY secret",
    )
    text = repr(spec)
    assert "super-secret" not in text
    assert "BEGIN KEY" not in text
    assert spec.location() == "sftp://nas.local:22/gens"
    assert "alice" not in spec.location()
    spec.clear_secrets()
    assert spec.password is None
    assert spec.private_key is None
    assert redact("super-secret") == "***"


def test_smb_requires_share_name():
    spec = ShareSpec(protocol="smb", host="files.local", path="")
    with pytest.raises(ShareError, match="share name"):
        spec.location()  # location itself is fine
        from clonebins_api.shares import _smb_unc

        _smb_unc(spec)


def test_smb_unc_join():
    from clonebins_api.shares import _smb_join, _smb_unc

    spec = ShareSpec(protocol="smb", host="files.local", path="Photos/gens")
    assert _smb_unc(spec) == r"\\files.local\Photos\gens"
    assert _smb_join(r"\\files.local\Photos", "gens", "a.png") == r"\\files.local\Photos\gens\a.png"


def test_fetch_share_copies_via_stub(tmp_path, monkeypatch):
    remote = tmp_path / "remote"
    remote.mkdir()
    (remote / "hero.png").write_bytes(b"png-bytes")
    (remote / "notes.txt").write_text("ignore")
    dest = tmp_path / "cache"
    spec = ShareSpec(protocol="sftp", host="example", path="/data", password="hidden")
    logs: list[str] = []

    def fake_fetch(inner_spec, inner_dest, log=None):
        assert inner_spec.password == "hidden"
        for path in remote.iterdir():
            if path.suffix == ".png":
                target = Path(inner_dest) / path.name
                target.write_bytes(path.read_bytes())
                if log:
                    log(f"Cached {path.name}")
        inner_spec.clear_secrets()
        return 1

    monkeypatch.setattr("clonebins_api.shares._fetch_sftp", lambda spec, dest, log=None: fake_fetch(spec, dest, log))
    n = fetch_share(spec, dest, log=logs.append)
    assert n == 1
    assert (dest / "hero.png").read_bytes() == b"png-bytes"
    assert spec.password is None
    assert all("hidden" not in line for line in logs)


def test_probe_share_does_not_keep_files(tmp_path, monkeypatch):
    spec = ShareSpec(protocol="ftp", host="ftp.local", password="pw")

    def fake_iter(_spec, log=None):
        yield "a.jpg", 10
        yield "b.png", 10

    monkeypatch.setattr("clonebins_api.shares._iter_images", fake_iter)
    result = probe_share(spec)
    assert result["ok"] is True
    assert result["images"] == 2
    assert spec.password is None
    assert "pw" not in result["location"]


def test_rejects_unknown_protocol():
    with pytest.raises(ShareError):
        ShareSpec(protocol="http", host="x")  # type: ignore[arg-type]
