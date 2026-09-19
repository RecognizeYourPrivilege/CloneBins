from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IOS = ROOT / "apps" / "ios"


def _read(relative: str) -> str:
    path = IOS / relative
    assert path.is_file(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def test_xcodegen_project_targets_ios_17():
    spec = _read("project.yml")
    assert "iOS: \"17.0\"" in spec or "iOS: '17.0'" in spec
    assert "PRODUCT_BUNDLE_IDENTIFIER: dev.clonebins.ios" in spec
    assert "INFOPLIST_FILE: CloneBins/Info.plist" in spec
    assert "ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon" in spec
    assert "type: application" in spec
    assert "platform: iOS" in spec


def test_swiftui_app_entry_and_views_exist():
    for relative in (
        "CloneBins/CloneBinsApp.swift",
        "CloneBins/Info.plist",
        "CloneBins/Models/APIModels.swift",
        "CloneBins/Services/CloneBinsAPIClient.swift",
        "CloneBins/Services/EmbeddingBackend.swift",
        "CloneBins/Services/ImageImport.swift",
        "CloneBins/ViewModels/AppModel.swift",
        "CloneBins/Views/RootView.swift",
        "CloneBins/Views/SettingsPane.swift",
        "CloneBins/Views/ClusterViews.swift",
        "CloneBins/Assets.xcassets/AppIcon.appiconset/AppIcon.png",
        "README.md",
        "project.yml",
    ):
        assert (IOS / relative).is_file(), relative


def test_api_client_matches_fastapi_routes():
    client = _read("CloneBins/Services/CloneBinsAPIClient.swift")
    for path in (
        "/api/health",
        "/api/jobs/upload",
        "/api/jobs/",
        "/cluster",
        "/cancel",
        "/include",
        "/merge",
        "/exclude",
        "/thumbs/",
        "/export.zip",
    ):
            assert path in client, path
    assert "multipart/form-data" in client
    assert 'name=\\"files\\"' in client


def test_multipart_field_is_files():
    client = _read("CloneBins/Services/CloneBinsAPIClient.swift")
    assert 'name=\\"files\\"' in client


def test_settings_mirror_web():
    models = _read("CloneBins/Models/APIModels.swift")
    settings = _read("CloneBins/Views/SettingsPane.swift")
    assert 'case faceBody = "face+body"' in models
    assert "min_images" in models
    assert "subject_prefix" in models
    assert "download_models" in models
    assert "keep_names" in models
    assert "Similarity threshold" in settings
    assert "Min images per bin" in settings
    assert "Picker(\"Mode\"" in settings or "Mode" in settings
    assert "API base URL" in settings
    assert "CLONEBINS_API_HOST=0.0.0.0" in settings
    assert "face+body" in models


def test_photos_files_import_and_share_sheet():
    root = _read("CloneBins/Views/RootView.swift")
    app_model = _read("CloneBins/ViewModels/AppModel.swift")
    assert "PhotosPicker" in root
    assert "fileImporter" in root
    assert "ShareSheet" in root
    assert "UIActivityViewController" in root
    assert "clonebins.zip" in app_model
    assert "ImageImport.uploadFiles" in app_model
    import_src = _read("CloneBins/Services/ImageImport.swift")
    assert "image/webp" in import_src
    assert "transcodeToJPEG" in import_src


def test_cluster_preview_rename_merge():
    clusters = _read("CloneBins/Views/ClusterViews.swift")
    assert "AsyncImage" in clusters
    assert "thumbnailURL" in clusters
    assert "Rename" in clusters
    assert "Merge selected" in clusters
    assert "in zip" in clusters


def test_core_ml_is_stubbed():
    backend = _read("CloneBins/Services/EmbeddingBackend.swift")
    assert "protocol IdentityBackend" in backend
    assert "protocol OnDeviceEmbeddingBackend" in backend
    assert "struct CoreMLIdentityBackend" in backend
    assert "coreMLUnavailable" in backend
    assert "struct RemotePythonBackend" in backend
    assert "isAvailable = false" in backend


def test_privacy_plist_local_only():
    plist = _read("CloneBins/Info.plist")
    assert "NSAllowsLocalNetworking" in plist
    assert "NSPhotoLibraryUsageDescription" in plist
    assert "NSLocalNetworkUsageDescription" in plist
    assert "NSAllowsArbitraryLoads" not in plist
    assert "vendor cloud" in plist.lower() or "cloud account" in plist.lower()


def test_ios_readme_has_mac_run_steps():
    readme = _read("README.md")
    assert "xcodegen generate" in readme
    assert "open CloneBins.xcodeproj" in readme
    assert "CLONEBINS_API_HOST=0.0.0.0" in readme
    assert "127.0.0.1:8765" in readme
    assert "Core ML" in readme
    assert "cannot sign" in readme.lower() or "cannot compile" in readme.lower()


def test_root_docs_no_longer_call_ios_a_placeholder():
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "| `apps/ios` | placeholder" not in root_readme
    assert "apps/ios/          placeholder" not in root_readme
    assert "placeholder (SwiftUI later)" not in architecture
    assert "iOS remains a stub" not in architecture
    assert "SwiftUI" in root_readme
    assert "XcodeGen" in architecture or "xcodegen" in architecture.lower()
    assert "Core ML" in architecture
