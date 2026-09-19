from __future__ import annotations

import pytest

from clonebins_core.embed.sface import SFaceEmbedder
from clonebins_core.io import load_image_bgr
from clonebins_core.models import models_present, resolve_model_paths
from portraits import write_portrait


@pytest.mark.skipif(not models_present(), reason="YuNet/SFace weights not cached")
def test_sface_loads_and_handles_nonface(tmp_path):
    paths = resolve_model_paths()
    embedder = SFaceEmbedder(paths)
    portrait = tmp_path / "geom.png"
    write_portrait(portrait, bg=(200, 40, 40), shirt=(160, 20, 20), seed=1)
    result = embedder.embed(load_image_bgr(portrait))
    # Geometric fixtures are not real faces; the backend must not crash.
    assert result.faces_found == 0
    assert result.embedding is None
