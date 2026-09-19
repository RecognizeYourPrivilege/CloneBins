"""Shared synthetic portraits for pipeline tests (no real photos, no models)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def write_portrait(path: Path, *, bg: tuple[int, int, int], shirt: tuple[int, int, int], seed: int) -> None:
    """Simple geometric 'person' so appearance clustering has a signal."""
    img = Image.new("RGB", (256, 320), bg)
    draw = ImageDraw.Draw(img)
    # large shirt block so palette dominates the embedding
    draw.rectangle([16, 140, 240, 320], fill=shirt)
    # small head (shared skin tone should not merge different palettes)
    draw.ellipse([96, 36, 160, 108], fill=(224, 186, 152))
    hair = (max(10, bg[0] // 4), max(10, bg[1] // 4), max(10, bg[2] // 4))
    draw.pieslice([90, 24, 166, 80], start=180, end=0, fill=hair)
    jitter = seed % 8
    draw.ellipse([108, 62, 118, 72], fill=(30, 30, 30))
    draw.ellipse([138, 62, 148, 72], fill=(30, 30, 30))
    draw.rectangle([20 + jitter, 300, 60 + jitter, 312], fill=tuple(min(255, c + 20) for c in shirt))
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
