"""README must show the demo video and Docker quick start on GitHub."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_embeds_github_safe_demo_media() -> None:
    assert "docs/demo/web_ui_clusters_zip.png" in README
    assert "docs/demo/web_cluster_rename_zip.gif" in README
    assert "docs/demo/web_cluster_rename_zip.mp4" in README
    # Markdown images render on github.com; HTML <img> is flaky in READMEs.
    assert "<img " not in README
    gif = ROOT / "docs/demo/web_cluster_rename_zip.gif"
    mp4 = ROOT / "docs/demo/web_cluster_rename_zip.mp4"
    png = ROOT / "docs/demo/web_ui_clusters_zip.png"
    assert gif.is_file() and mp4.is_file() and png.is_file()
    # GitHub's image proxy often drops multi-megabyte GIFs.
    assert gif.stat().st_size < 1_500_000
    assert gif.read_bytes()[:6] == b"GIF89a"
    assert mp4.read_bytes()[4:8] == b"ftyp"


def test_readme_has_docker_quick_start() -> None:
    assert "## Docker (web UI)" in README
    # Primary path is the prebuilt GHCR image, not a local build.
    assert (
        'docker run --rm -p 8765:8765 -v "$HOME/gens:/data:ro" '
        "ghcr.io/recognizeyourprivilege/clonebins:latest"
    ) in README
    assert "docker compose pull" in README
    assert "docker compose up" in README
    # Contributor path stays documented after the pull instructions.
    assert "docker compose up --build" in README
    assert README.index("ghcr.io/recognizeyourprivilege/clonebins:latest") < README.index(
        "docker compose up --build"
    )
    assert "http://127.0.0.1:8765" in README
    assert "[`Dockerfile`](Dockerfile)" in README
    assert "[`docker-compose.yml`](docker-compose.yml)" in README
    assert (ROOT / "Dockerfile").is_file()
    assert (ROOT / "docker-compose.yml").is_file()
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "image: ghcr.io/recognizeyourprivilege/clonebins:latest" in compose
    assert "${HOME}/gens:/data:ro" in compose
    assert "8765:8765" in compose
    assert "CLONEBINS_API_HOST" in compose
    assert "CLONEBINS_API_PORT" in compose
    assert "CLONEBINS_MODELS_DIR" in compose
    assert "CLONEBINS_WEB_DIST" in compose
    # `build: .` stays available for contributors, but not as an active key.
    assert "# build: ." in compose
    assert "\n    build:" not in compose
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "clonebins-api" in dockerfile
    assert "clonebins_core.models --all" in dockerfile


def test_readme_does_not_include_alpine() -> None:
    assert "alpine" not in README.lower()
    assert "Alpine" not in README
