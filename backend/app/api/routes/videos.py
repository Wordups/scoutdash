import shutil
import subprocess
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
from app.services.storage import local_file_path, save_upload
from app.services.video import extract_sampled_frames, probe_video


router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("", response_model=list[VideoRead])
def list_videos(
    organization_id: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[VideoModel]:
    statement = select(VideoModel)
    if organization_id:
        statement = statement.where(VideoModel.organization_id == organization_id)
    if team_id:
        statement = statement.where(VideoModel.team_id == team_id)
    if event_id:
        statement = statement.where(VideoModel.event_id == event_id)
    return list(db.scalars(statement.order_by(VideoModel.created_at.desc())))


@router.post("", response_model=VideoRead, status_code=201)
def create_video(payload: VideoCreate, db: Session = Depends(get_db)) -> VideoModel:
    _validate_video_scope(db, payload.organization_id, payload.team_id, payload.event_id)
    video = VideoModel(**payload.model_dump())
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@router.post("/from-url", response_model=VideoRead, status_code=201)
def import_video_url(payload: VideoUrlImport, db: Session = Depends(get_db)) -> VideoModel:
    _validate_video_scope(db, payload.organization_id, payload.team_id, payload.event_id)
    parsed = urlparse(payload.source_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Only http and https video URLs are supported")

    settings = get_settings()
    suffix = _suffix_from_url(parsed.path)
    storage_key = f"{payload.organization_id}/{payload.team_id}/{uuid4()}{suffix}"
    destination = local_file_path(settings, storage_key)
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with httpx.stream("GET", payload.source_url, follow_redirects=True, timeout=30) as response:
            response.raise_for_status()
            with destination.open("wb") as output:
                for chunk in response.iter_bytes():
                    output.write(chunk)
    except (httpx.HTTPError, OSError) as exc:
        if destination.exists():
            destination.unlink()
        raise HTTPException(status_code=400, detail=f"Could not import video URL: {exc}") from exc

    metadata = probe_video(destination)
    video = VideoModel(
        organization_id=payload.organization_id,
        team_id=payload.team_id,
        event_id=payload.event_id,
        title=payload.title,
        original_filename=payload.source_url,
        content_type="video/url-import",
        storage_backend="local",
        storage_key=storage_key,
        storage_url=f"{settings.public_media_base_url.rstrip('/')}/{storage_key}" if settings.public_media_base_url else None,
        **metadata,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@router.post("/upload", response_model=VideoRead, status_code=201)
def upload_video(
    organization_id: str = Form(...),
    team_id: str = Form(...),
    event_id: str | None = Form(default=None),
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> VideoModel:
    _validate_video_scope(db, organization_id, team_id, event_id)
    settings = get_settings()
    stored = save_upload(file, settings, organization_id, team_id)

    metadata = {"duration_seconds": None, "fps": None, "frame_count": None}
    if stored.backend == "local":
        metadata = probe_video(local_file_path(settings, stored.key))

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
    return video


@router.get("/{video_id}", response_model=VideoRead)
def get_video(video_id: str, db: Session = Depends(get_db)) -> VideoModel:
    video = db.get(VideoModel, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.post("/{video_id}/process", response_model=VideoProcessRead)
def process_video(
    video_id: str,
    payload: VideoProcessRequest | None = None,
    db: Session = Depends(get_db),
) -> VideoProcessRead:
    video = db.get(VideoModel, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.storage_backend != "local":
        raise HTTPException(status_code=400, detail="Only local video files can be processed")

    settings = get_settings()
    video_path = local_file_path(settings, video.storage_key)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on local storage")

    request = payload or VideoProcessRequest()
    frame_dir = settings.local_upload_dir / "frames" / video.id
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    db.query(VideoFrameModel).filter(VideoFrameModel.video_id == video.id).delete()

    try:
        extracted = extract_sampled_frames(
            video_path,
            frame_dir,
            sample_fps=request.sample_fps,
            max_frames=request.max_frames,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not process video: {exc}") from exc

    metadata = probe_video(video_path)
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
        video=VideoRead.model_validate(video),
        frames=[_frame_read(model) for model in frame_models],
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
    return [_frame_read(frame) for frame in frames]


def _validate_video_scope(db: Session, organization_id: str, team_id: str, event_id: str | None) -> None:
    team = db.get(TeamModel, team_id)
    if team is None or team.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Team not found for organization")
    if event_id:
        event = db.get(EventModel, event_id)
        if event is None or event.team_id != team_id:
            raise HTTPException(status_code=404, detail="Event not found for team")


def _frame_read(frame: VideoFrameModel) -> VideoFrameRead:
    settings = get_settings()
    frame_url = None
    if settings.public_media_base_url:
        frame_url = f"{settings.public_media_base_url.rstrip('/')}/{frame.storage_key}"
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
