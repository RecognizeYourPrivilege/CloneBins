"""Shared synthetic portraits for pipeline tests (no real photos, no models)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def write_portrait(path: Path, *, bg: tuple[int, int, int], shirt: tuple[int, int, int], seed: int) -> None:
    """Simple geometric 'person' so appearance clustering has a signal."""
    img = Image.new("RGB", (256, 320), bg)
    draw = ImageDraw.Draw(img)
    # body / shirt
    draw.rectangle([48, 190, 208, 320], fill=shirt)
    # head
    draw.ellipse([78, 40, 178, 160], fill=(224, 186, 152))
    # hair — slightly vary by seed so files are not byte-identical
    hair = (40 + (seed * 7) % 30, 30, 24)
    draw.pieslice([70, 28, 186, 120], start=180, end=0, fill=hair)
    # eyes
    draw.ellipse([104, 88, 118, 102], fill=(30, 30, 30))
    draw.ellipse([138, 88, 152, 102], fill=(30, 30, 30))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def write_identity_set(root: Path) -> dict[str, list[Path]]:
    """Two identities (red vs blue) × three images each."""
    red_bg = (196, 64, 48)
    blue_bg = (48, 72, 196)
    red_shirt = (160, 32, 32)
    blue_shirt = (32, 48, 160)
    out: dict[str, list[Path]] = {"red": [], "blue": []}
    for i in range(3):
        p = root / f"red_{i+1:02d}.png"
        write_portrait(p, bg=red_bg, shirt=red_shirt, seed=10 + i)
        out["red"].append(p)
    for i in range(3):
        p = root / f"blue_{i+1:02d}.png"
        write_portrait(p, bg=blue_bg, shirt=blue_shirt, seed=20 + i)
        out["blue"].append(p)
    return out
