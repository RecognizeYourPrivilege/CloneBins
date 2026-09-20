"""Pydantic request/response models for the local API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

YunNetId = Literal["2023mar", "2023mar_int8", "2023mar_int8bq"]
SFaceId = Literal["2021dec", "2021dec_int8", "2021dec_int8bq"]


class ClusterSettings(BaseModel):
    threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    min_images: int = Field(default=2, ge=1)
    mode: Literal["face", "face+body"] = "face+body"
    subject_prefix: str = "subject"
    download_models: bool = True
    keep_names: bool = True
    yunet: YunNetId = "2023mar"
    sface: SFaceId = "2021dec"


class PathRequest(BaseModel):
    path: str


class RenameRequest(BaseModel):
    name: str


class MergeRequest(BaseModel):
    cluster_ids: list[str]


class ExtractRequest(BaseModel):
    image_ids: list[str]


class ExcludeRequest(BaseModel):
    image_ids: list[str]


class IncludeRequest(BaseModel):
    included: bool


class ShareRequest(BaseModel):
    protocol: Literal["smb", "sftp", "ftp"]
    host: str
    path: str = ""
    username: str = ""
    password: str | None = None
    private_key: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)


class ModelDownloadRequest(BaseModel):
    yunet: YunNetId = "2023mar"
    sface: SFaceId = "2021dec"
    all_variants: bool = True


class ImageOut(BaseModel):
    id: str
    filename: str
    skipped: bool = False
    skip_reason: str | None = None
    unmatched: bool = False
    unmatched_reason: str | None = None


class ClusterOut(BaseModel):
    id: str
    name: str
    image_ids: list[str]
    included: bool = True
    below_min: bool = False


class ProgressOut(BaseModel):
    phase: str = ""
    completed: int = 0
    total: int = 0
    detail: str = ""
    logs: list[str] = Field(default_factory=list)


class JobOut(BaseModel):
    id: str
    status: str
    source: str
    settings: ClusterSettings | None = None
    progress: ProgressOut
    clusters: list[ClusterOut] = Field(default_factory=list)
    images: list[ImageOut] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    backend_name: str = ""
    scanned: int = 0
    error: str | None = None
