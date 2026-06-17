from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import ClipModel, EvidenceTagModel, VideoModel
from app.schemas import ClipCreate, ClipRead


router = APIRouter(prefix="/clips", tags=["clips"])


@router.get("", response_model=list[ClipRead])
def list_clips(
    video_id: str | None = Query(default=None),
    athlete_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ClipModel]:
    statement = select(ClipModel)
    if video_id:
        statement = statement.where(ClipModel.video_id == video_id)
    if athlete_id:
        statement = statement.join(EvidenceTagModel, EvidenceTagModel.clip_id == ClipModel.id).where(
            EvidenceTagModel.athlete_id == athlete_id
        )
    return list(db.scalars(statement.order_by(ClipModel.created_at.desc())).unique())


@router.post("", response_model=ClipRead, status_code=201)
def create_clip(payload: ClipCreate, db: Session = Depends(get_db)) -> ClipModel:
    video = db.get(VideoModel, payload.video_id)
    if video is None or video.organization_id != payload.organization_id or video.team_id != payload.team_id:
        raise HTTPException(status_code=404, detail="Video not found for organization/team")
    clip = ClipModel(**payload.model_dump())
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip
