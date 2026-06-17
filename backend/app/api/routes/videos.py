import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.models import EventModel, TeamModel, VideoFrameModel, VideoModel
from app.schemas import VideoCreate, VideoFrameRead, VideoProcessRead, VideoProcessRequest, VideoRead, VideoUrlImport
from botocore.exceptions import BotoCoreError, ClientError

from app.services.storage import delete_prefix, materialize_file, save_path, save_upload, storage_url
from app.services.video import VideoProcessingError, extract_sampled_frames, probe_video


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
def create_video(payload: VideoCreate, db: Session = Depends(get_db)) -> VideoModel:
    _validate_video_scope(db, payload.organization_id, payload.team_id, payload.event_id)
    video = VideoModel(**payload.model_dump())
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


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
            metadata = probe_video(destination, settings)
            stored = save_path(destination, settings, storage_key, content_type)
    except (httpx.HTTPError, OSError, ValueError, BotoCoreError, ClientError) as exc:
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
    stored = save_upload(file, settings, organization_id, team_id)

    metadata = {"duration_seconds": None, "fps": None, "frame_count": None}
    try:
        with materialize_file(settings, stored.backend, stored.key) as video_path:
            metadata = probe_video(video_path, settings)
    except (FileNotFoundError, ValueError, BotoCoreError, ClientError):
        pass

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


@router.post("/{video_id}/process", response_model=VideoProcessRead)
def process_video(
    video_id: str,
    payload: VideoProcessRequest | None = None,
    db: Session = Depends(get_db),
) -> VideoProcessRead:
    video = db.get(VideoModel, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    settings = get_settings()
    request = payload or VideoProcessRequest()
    try:
        with materialize_file(settings, video.storage_backend, video.storage_key) as video_path:
            metadata = probe_video(video_path, settings)
            with tempfile.TemporaryDirectory(prefix="scoutdash-frames-") as temporary_dir:
                extracted = extract_sampled_frames(
                    video_path,
                    Path(temporary_dir),
                    settings,
                    sample_fps=request.sample_fps,
                    max_frames=request.max_frames,
                )
                delete_prefix(settings, video.storage_backend, f"frames/{video.id}")
                for frame in extracted:
                    save_path(
                        frame.path,
                        settings,
                        f"frames/{video.id}/{frame.path.name}",
                        "image/jpeg",
                        backend=video.storage_backend,
                    )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="The stored video file is missing. Upload the film again.") from exc
    except (VideoProcessingError, subprocess.SubprocessError, ValueError, BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not process video: {exc}") from exc

    db.query(VideoFrameModel).filter(VideoFrameModel.video_id == video.id).delete()
    video.duration_seconds = metadata["duration_seconds"]
    video.fps = metadata["fps"]
    video.frame_count = metadata["frame_count"]

    frame_models: list[VideoFrameModel] = []
    for frame in extracted:
        storage_key = f"frames/{video.id}/{frame.path.name}"
        model = VideoFrameModel(
            video_id=video.id,
            frame_number=frame.frame_number,
            timestamp_seconds=frame.timestamp_seconds,
            storage_key=storage_key,
            width=frame.width,
            height=frame.height,
        )
        db.add(model)
        frame_models.append(model)

    db.commit()
    db.refresh(video)
    for model in frame_models:
        db.refresh(model)

    return VideoProcessRead(
        video=_video_read(video),
        frames=[_frame_read(model, video) for model in frame_models],
        frame_count_extracted=len(frame_models),
    )


@router.get("/{video_id}/frames", response_model=list[VideoFrameRead])
def list_video_frames(video_id: str, db: Session = Depends(get_db)) -> list[VideoFrameRead]:
    if db.get(VideoModel, video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found")
    frames = list(
        db.scalars(
            select(VideoFrameModel)
            .where(VideoFrameModel.video_id == video_id)
            .order_by(VideoFrameModel.frame_number.asc())
        )
    )
    video = db.get(VideoModel, video_id)
    return [_frame_read(frame, video) for frame in frames]


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
