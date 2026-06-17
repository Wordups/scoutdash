from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.models import EventModel, TeamModel, VideoModel
from app.schemas import VideoCreate, VideoRead
from app.services.storage import local_file_path, save_upload
from app.services.video import probe_video


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


def _validate_video_scope(db: Session, organization_id: str, team_id: str, event_id: str | None) -> None:
    team = db.get(TeamModel, team_id)
    if team is None or team.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Team not found for organization")
    if event_id:
        event = db.get(EventModel, event_id)
        if event is None or event.team_id != team_id:
            raise HTTPException(status_code=404, detail="Event not found for team")

