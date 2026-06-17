from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings


class StoredFile:
    def __init__(self, backend: str, key: str, url: str | None) -> None:
        self.backend = backend
        self.key = key
        self.url = url


def save_upload(file: UploadFile, settings: Settings, organization_id: str, team_id: str) -> StoredFile:
    suffix = _safe_suffix(file.filename)
    storage_key = f"{organization_id}/{team_id}/{uuid4()}{suffix}"
    if settings.storage_backend == "s3":
        client = _s3_client(settings)
        _require_s3_bucket(settings)
        client.upload_fileobj(
            file.file,
            settings.s3_bucket,
            storage_key,
            ExtraArgs={"ContentType": file.content_type or "application/octet-stream"},
        )
        return StoredFile(backend="s3", key=storage_key, url=None)

    destination = local_file_path(settings, storage_key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    return StoredFile(backend="local", key=storage_key, url=storage_url(settings, "local", storage_key))


def save_path(
    path: Path,
    settings: Settings,
    storage_key: str,
    content_type: str,
    backend: str | None = None,
) -> StoredFile:
    target_backend = backend or settings.storage_backend
    if target_backend == "s3":
        _require_s3_bucket(settings)
        _s3_client(settings).upload_file(
            str(path),
            settings.s3_bucket,
            storage_key,
            ExtraArgs={"ContentType": content_type},
        )
        return StoredFile(backend="s3", key=storage_key, url=None)

    if target_backend != "local":
        raise ValueError(f"Unsupported storage backend: {target_backend}")
    destination = local_file_path(settings, storage_key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() != destination.resolve():
        shutil.copy2(path, destination)
    return StoredFile(backend="local", key=storage_key, url=storage_url(settings, "local", storage_key))


@contextmanager
def materialize_file(settings: Settings, backend: str, storage_key: str) -> Iterator[Path]:
    if backend == "local":
        path = local_file_path(settings, storage_key)
        if not path.exists():
            raise FileNotFoundError(storage_key)
        yield path
        return

    if backend != "s3":
        raise ValueError(f"Unsupported storage backend: {backend}")

    _require_s3_bucket(settings)
    suffix = _safe_suffix(storage_key)
    with tempfile.TemporaryDirectory(prefix="scoutdash-video-") as temporary_dir:
        destination = Path(temporary_dir) / f"source{suffix}"
        _s3_client(settings).download_file(settings.s3_bucket, storage_key, str(destination))
        yield destination


def delete_prefix(settings: Settings, backend: str, prefix: str) -> None:
    if backend == "local":
        path = local_file_path(settings, prefix)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        return
    if backend != "s3":
        return

    _require_s3_bucket(settings)
    client = _s3_client(settings)
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=prefix):
        objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=settings.s3_bucket, Delete={"Objects": objects})


def storage_url(settings: Settings, backend: str, storage_key: str) -> str | None:
    normalized_key = storage_key.replace("\\", "/")
    if backend == "local":
        if not settings.public_media_base_url:
            return None
        return f"{settings.public_media_base_url.rstrip('/')}/{normalized_key}"
    if backend != "s3" or not settings.s3_bucket:
        return None

    client = _s3_client(settings, public=True)
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": normalized_key},
        ExpiresIn=settings.s3_presigned_url_ttl_seconds,
    )


def local_file_path(settings: Settings, storage_key: str) -> Path:
    root = settings.local_upload_dir.resolve()
    path = (root / storage_key).resolve()
    if root != path and root not in path.parents:
        raise ValueError("Storage key escapes the configured upload directory")
    return path


def _safe_suffix(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix and len(suffix) <= 12:
        return suffix
    return ".mp4"


def _require_s3_bucket(settings: Settings) -> None:
    if not settings.s3_bucket:
        raise ValueError("S3_BUCKET must be configured when STORAGE_BACKEND=s3")


def _s3_client(settings: Settings, public: bool = False):
    import boto3

    endpoint = settings.s3_public_endpoint_url if public and settings.s3_public_endpoint_url else settings.s3_endpoint_url
    return boto3.client(
        "s3",
        endpoint_url=str(endpoint) if endpoint else None,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
    )
