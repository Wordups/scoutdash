import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models import (
    EventModel,
    TeamModel,
    VideoFrameModel,
    VideoModel,
    VideoProcessingJobModel,
)
from app.schemas import (
    VideoCreate,
    VideoFrameRead,
    VideoProcessingJobRead,
    VideoProcessRequest,
    VideoRead,
    VideoReadinessRead,
    VideoUrlImport,
)
from app.services.film_metadata import capabilities, probe
from app.services.storage import (
    delete_keys,
    delete_prefix,
    materialize_file,
    object_exists,
    save_path,
    save_upload,
    storage_url,
)
from app.services.video import extract_sampled_frames


router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("", response_model=list[VideoRead])
def list_videos(
    organization_id: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[VideoRead]:
    statement = select(VideoModel)
    if organization_id:
        statement = statement.where(VideoModel.organization_id == organization_id)
    if team_id:
        statement = statement.where(VideoModel.team_id == team_id)
    if event_id:
        statement = statement.where(VideoModel.event_id == event_id)
    return [_video_read(video) for video in db.scalars(statement.order_by(VideoModel.created_at.desc()))]


@router.post("", response_model=VideoRead, status_code=201)
def create_video(payload: VideoCreate, db: Session = Depends(get_db)) -> VideoRead:
    _validate_video_scope(db, payload.organization_id, payload.team_id, payload.event_id)
    video = VideoModel(**payload.model_dump())
    db.add(video)
    db.commit()
    db.refresh(video)
    return _video_read(video)


@router.post("/from-url", response_model=VideoRead, status_code=201)
def import_video_url(payload: VideoUrlImport, db: Session = Depends(get_db)) -> VideoRead:
    _validate_video_scope(db, payload.organization_id, payload.team_id, payload.event_id)
    parsed = urlparse(payload.source_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Only http and https video URLs are supported")

    settings = get_settings()
    suffix = _suffix_from_url(parsed.path)
    storage_key = f"{payload.organization_id}/{payload.team_id}/{uuid4()}{suffix}"
    try:
        with tempfile.TemporaryDirectory(prefix="scoutdash-import-") as temporary_dir:
            destination = Path(temporary_dir) / f"source{suffix}"
            with httpx.stream("GET", payload.source_url, follow_redirects=True, timeout=60) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "video/mp4").split(";", maxsplit=1)[0]
                with destination.open("wb") as output:
                    for chunk in response.iter_bytes():
                        output.write(chunk)
            metadata = _video_metadata(probe(str(destination)))
            stored = save_path(destination, settings, storage_key, content_type)
    except (httpx.HTTPError, OSError, RuntimeError, ValueError, BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not import video URL: {exc}") from exc

    video = VideoModel(
        organization_id=payload.organization_id,
        team_id=payload.team_id,
        event_id=payload.event_id,
        title=payload.title,
        original_filename=payload.source_url,
        content_type=content_type,
        storage_backend=stored.backend,
        storage_key=stored.key,
        storage_url=stored.url,
        **metadata,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return _video_read(video)


@router.post("/upload", response_model=VideoRead, status_code=201)
def upload_video(
    organization_id: str = Form(...),
    team_id: str = Form(...),
    event_id: str | None = Form(default=None),
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> VideoRead:
    _validate_video_scope(db, organization_id, team_id, event_id)
    settings = get_settings()
    try:
        stored = save_upload(file, settings, organization_id, team_id)
    except (OSError, ValueError, BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=503, detail=f"Could not store film: {exc}") from exc

    try:
        with materialize_file(settings, stored.backend, stored.key) as video_path:
            metadata = _video_metadata(probe(str(video_path)))
    except (FileNotFoundError, OSError, RuntimeError, ValueError, BotoCoreError, ClientError) as exc:
        try:
            delete_keys(settings, stored.backend, [stored.key])
        except (OSError, ValueError, BotoCoreError, ClientError):
            pass
        raise HTTPException(
            status_code=400,
            detail=f"Could not read film details. Confirm the file is a playable video and upload it again. {exc}",
        ) from exc

    video = VideoModel(
        organization_id=organization_id,
        team_id=team_id,
        event_id=event_id,
        title=title,
        original_filename=file.filename,
        content_type=file.content_type,
        storage_backend=stored.backend,
        storage_key=stored.key,
        storage_url=stored.url,
        **metadata,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return _video_read(video)


@router.get("/{video_id}", response_model=VideoRead)
def get_video(video_id: str, db: Session = Depends(get_db)) -> VideoRead:
    video = db.get(VideoModel, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return _video_read(video)


@router.get("/{video_id}/readiness", response_model=VideoReadinessRead)
def get_video_readiness(video_id: str, db: Session = Depends(get_db)) -> VideoReadinessRead:
    video = db.get(VideoModel, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    settings = get_settings()
    try:
        file_available = object_exists(settings, video.storage_backend, video.storage_key)
    except (ValueError, BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=503, detail=f"Could not check film storage: {exc}") from exc

    processing_ready = bool(capabilities()["ready"])
    extracted_frame_count = db.query(VideoFrameModel).filter(VideoFrameModel.video_id == video.id).count()
    storage_persistent = video.storage_backend == "s3" or settings.local_storage_persistent
    active_job = db.scalar(
        select(VideoProcessingJobModel)
        .where(
            VideoProcessingJobModel.video_id == video.id,
            VideoProcessingJobModel.status.in_(("queued", "processing")),
        )
        .order_by(VideoProcessingJobModel.created_at.desc())
        .limit(1)
    )

    if not file_available:
        message = "The source film is missing. Upload the film again to continue."
    elif not processing_ready:
        message = "Film processing is temporarily unavailable."
    elif active_job:
        message = "Film breakdown is in progress."
    elif extracted_frame_count:
        message = f"Ready with {extracted_frame_count} review moments."
    else:
        message = "Ready to break down."

    return VideoReadinessRead(
        video_id=video.id,
        file_available=file_available,
        processing_ready=file_available and processing_ready,
        storage_persistent=storage_persistent,
        extracted_frame_count=extracted_frame_count,
        message=message,
    )


@router.post(
    "/{video_id}/process",
    response_model=VideoProcessingJobRead,
    status_code=202,
)
def process_video(
    video_id: str,
    background_tasks: BackgroundTasks,
    payload: VideoProcessRequest | None = None,
    db: Session = Depends(get_db),
) -> VideoProcessingJobModel:
    video = db.get(VideoModel, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    settings = get_settings()
    if not capabilities()["ready"]:
        raise HTTPException(status_code=503, detail="Film processing is temporarily unavailable.")
    try:
        source_available = object_exists(settings, video.storage_backend, video.storage_key)
    except (ValueError, BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=503, detail=f"Could not check film storage: {exc}") from exc
    if not source_available:
        raise HTTPException(status_code=404, detail="The stored video file is missing. Upload the film again.")

    active_job = db.scalar(
        select(VideoProcessingJobModel)
        .where(
            VideoProcessingJobModel.video_id == video.id,
            VideoProcessingJobModel.status.in_(("queued", "processing")),
        )
        .order_by(VideoProcessingJobModel.created_at.desc())
        .limit(1)
    )
    if active_job:
        return active_job

    request = payload or VideoProcessRequest()
    job = VideoProcessingJobModel(
        video_id=video.id,
        status="queued",
        sample_fps=request.sample_fps,
        max_frames=request.max_frames,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(_run_video_processing_job, job.id)
    return job


@router.get("/{video_id}/process-status", response_model=VideoProcessingJobRead)
def get_video_process_status(
    video_id: str,
    db: Session = Depends(get_db),
) -> VideoProcessingJobModel:
    if db.get(VideoModel, video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found")
    job = db.scalar(
        select(VideoProcessingJobModel)
        .where(VideoProcessingJobModel.video_id == video_id)
        .order_by(VideoProcessingJobModel.created_at.desc())
        .limit(1)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="No film breakdown has been started.")
    return job


@router.get("/{video_id}/frames", response_model=list[VideoFrameRead])
def list_video_frames(video_id: str, db: Session = Depends(get_db)) -> list[VideoFrameRead]:
    video = db.get(VideoModel, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    frames = list(
        db.scalars(
            select(VideoFrameModel)
            .where(VideoFrameModel.video_id == video_id)
            .order_by(VideoFrameModel.frame_number.asc())
        )
    )
    return [_frame_read(frame, video) for frame in frames]


def _run_video_processing_job(job_id: str) -> None:
    settings = get_settings()
    frame_set_prefix = ""
    old_frame_keys: list[str] = []

    with SessionLocal() as db:
        job = db.get(VideoProcessingJobModel, job_id)
        if job is None:
            return
        video = db.get(VideoModel, job.video_id)
        if video is None:
            _fail_job(db, job, "Film record no longer exists.")
            return

        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        db.commit()

        frame_set_prefix = f"frames/{video.id}/{uuid4().hex}"
        old_frames = list(db.scalars(select(VideoFrameModel).where(VideoFrameModel.video_id == video.id)))
        old_frame_keys = [frame.storage_key for frame in old_frames]
        stored_frame_keys: list[str] = []

        try:
            with materialize_file(settings, video.storage_backend, video.storage_key) as video_path:
                metadata = _video_metadata(probe(str(video_path)))
                with tempfile.TemporaryDirectory(prefix="scoutdash-frames-") as temporary_dir:
                    extracted = extract_sampled_frames(
                        video_path,
                        Path(temporary_dir),
                        settings,
                        sample_fps=job.sample_fps,
                        max_frames=job.max_frames,
                    )
                    for frame in extracted:
                        storage_key = f"{frame_set_prefix}/{frame.path.name}"
                        save_path(
                            frame.path,
                            settings,
                            storage_key,
                            "image/jpeg",
                            backend=video.storage_backend,
                        )
                        stored_frame_keys.append(storage_key)

            db.query(VideoFrameModel).filter(VideoFrameModel.video_id == video.id).delete()
            _apply_video_metadata(video, metadata)
            for frame, storage_key in zip(extracted, stored_frame_keys, strict=True):
                db.add(
                    VideoFrameModel(
                        video_id=video.id,
                        frame_number=frame.frame_number,
                        timestamp_seconds=frame.timestamp_seconds,
                        storage_key=storage_key,
                        width=frame.width,
                        height=frame.height,
                    )
                )

            job.status = "completed"
            job.frame_count_extracted = len(extracted)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        except FileNotFoundError:
            db.rollback()
            _delete_frame_prefix(settings, video.storage_backend, frame_set_prefix)
            failed_job = db.get(VideoProcessingJobModel, job_id)
            if failed_job:
                _fail_job(db, failed_job, "The source film is missing. Upload the film again.")
            return
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            _delete_frame_prefix(settings, video.storage_backend, frame_set_prefix)
            failed_job = db.get(VideoProcessingJobModel, job_id)
            if failed_job:
                _fail_job(db, failed_job, f"Could not break down film: {str(exc)[-1200:]}")
            return

        try:
            delete_keys(settings, video.storage_backend, old_frame_keys)
        except (OSError, ValueError, BotoCoreError, ClientError):
            pass


def _delete_frame_prefix(settings: Settings, backend: str, prefix: str) -> None:
    try:
        delete_prefix(settings, backend, prefix)
    except (OSError, ValueError, BotoCoreError, ClientError):
        pass


def _fail_job(db: Session, job: VideoProcessingJobModel, message: str) -> None:
    job.status = "failed"
    job.error_message = message
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


def _video_metadata(metadata: dict[str, object]) -> dict[str, object]:
    return {
        "duration_seconds": metadata.get("duration_seconds"),
        "fps": metadata.get("fps"),
        "frame_count": metadata.get("frame_count"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "codec": metadata.get("codec"),
        "container_format": metadata.get("format"),
        "creation_time": metadata.get("creation_time"),
    }


def _apply_video_metadata(video: VideoModel, metadata: dict[str, object]) -> None:
    video.duration_seconds = metadata["duration_seconds"]  # type: ignore[assignment]
    video.fps = metadata["fps"]  # type: ignore[assignment]
    video.frame_count = metadata["frame_count"]  # type: ignore[assignment]
    video.width = metadata["width"]  # type: ignore[assignment]
    video.height = metadata["height"]  # type: ignore[assignment]
    video.codec = metadata["codec"]  # type: ignore[assignment]
    video.container_format = metadata["container_format"]  # type: ignore[assignment]
    video.creation_time = metadata["creation_time"]  # type: ignore[assignment]


def _validate_video_scope(db: Session, organization_id: str, team_id: str, event_id: str | None) -> None:
    team = db.get(TeamModel, team_id)
    if team is None or team.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Team not found for organization")
    if event_id:
        event = db.get(EventModel, event_id)
        if event is None or event.team_id != team_id:
            raise HTTPException(status_code=404, detail="Event not found for team")


def _video_read(video: VideoModel) -> VideoRead:
    data = VideoRead.model_validate(video)
    return data.model_copy(
        update={"storage_url": storage_url(get_settings(), video.storage_backend, video.storage_key)}
    )


def _frame_read(frame: VideoFrameModel, video: VideoModel | None = None) -> VideoFrameRead:
    settings = get_settings()
    backend = video.storage_backend if video else settings.storage_backend
    frame_url = storage_url(settings, backend, frame.storage_key)
    return VideoFrameRead(
        id=frame.id,
        video_id=frame.video_id,
        frame_number=frame.frame_number,
        timestamp_seconds=frame.timestamp_seconds,
        storage_key=frame.storage_key,
        frame_url=frame_url,
        width=frame.width,
        height=frame.height,
        created_at=frame.created_at,
        updated_at=frame.updated_at,
    )


def _suffix_from_url(path: str) -> str:
    lower = path.lower()
    for suffix in [".mp4", ".mov", ".m4v", ".webm"]:
        if lower.endswith(suffix):
            return suffix
    return ".mp4"
