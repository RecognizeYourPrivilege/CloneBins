from __future__ import annotations

from pathlib import Path

from clonebins_core.scan import scan_images
from portraits import write_identity_set


def test_scan_recursive_and_extensions(tmp_path: Path):
    nested = tmp_path / "a" / "b"
    write_identity_set(nested)
    (tmp_path / "notes.txt").write_text("ignore me")
    (tmp_path / "a" / "photo.JPG").write_bytes((nested / "red_01.png").read_bytes())
    found = scan_images(tmp_path)
    suffixes = {p.suffix.lower() for p in found}
    assert ".png" in suffixes
    assert ".jpg" in suffixes
    assert all(p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} for p in found)
    names = {p.name.lower() for p in found}
    assert "notes.txt" not in names
    assert "photo.jpg" in names
