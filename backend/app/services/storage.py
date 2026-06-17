from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings


class StoredFile:
    def __init__(self, backend: str, key: str, url: str | None) -> None:
        self.backend = backend
        self.key = key
        self.url = url


def _safe_suffix(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix and len(suffix) <= 12:
        return suffix
    return ".mp4"


def _public_url(settings: Settings, storage_key: str) -> str | None:
    if not settings.public_media_base_url:
        return None
    normalized_key = storage_key.replace("\\", "/")
    return f"{settings.public_media_base_url.rstrip('/')}/{normalized_key}"


def save_upload(file: UploadFile, settings: Settings, organization_id: str, team_id: str) -> StoredFile:
    if settings.storage_backend != "local":
        return _save_s3_upload(file, settings, organization_id, team_id)

    suffix = _safe_suffix(file.filename)
    storage_key = f"{organization_id}/{team_id}/{uuid4()}{suffix}"
    destination = settings.local_upload_dir / storage_key
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    return StoredFile(backend="local", key=storage_key, url=_public_url(settings, storage_key))


def _save_s3_upload(file: UploadFile, settings: Settings, organization_id: str, team_id: str) -> StoredFile:
    import boto3

    if not settings.s3_bucket:
        raise ValueError("S3_BUCKET must be configured when STORAGE_BACKEND=s3")

    suffix = _safe_suffix(file.filename)
    storage_key = f"{organization_id}/{team_id}/{uuid4()}{suffix}"
    client = boto3.client(
        "s3",
        endpoint_url=str(settings.s3_endpoint_url) if settings.s3_endpoint_url else None,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
    )
    client.upload_fileobj(file.file, settings.s3_bucket, storage_key, ExtraArgs={"ContentType": file.content_type})
    return StoredFile(backend="s3", key=storage_key, url=None)


def local_file_path(settings: Settings, storage_key: str) -> Path:
    return settings.local_upload_dir / storage_key
