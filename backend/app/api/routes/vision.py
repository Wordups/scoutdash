from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import AthleteModel, OrganizationModel, VideoModel, VisionTrackModel
from app.schemas import VisionManualSelection, VisionManualSelectionRead, VisionTrackCreate, VisionTrackRead


router = APIRouter(prefix="/vision", tags=["vision"])


@router.get("/tracks", response_model=list[VisionTrackRead])
def list_tracks(
    organization_id: str | None = Query(default=None),
    video_id: str | None = Query(default=None),
    athlete_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[VisionTrackModel]:
    statement = select(VisionTrackModel)
    if organization_id:
        statement = statement.where(VisionTrackModel.organization_id == organization_id)
    if video_id:
        statement = statement.where(VisionTrackModel.video_id == video_id)
    if athlete_id:
        statement = statement.where(VisionTrackModel.athlete_id == athlete_id)
    return list(db.scalars(statement.order_by(VisionTrackModel.created_at.desc())))


@router.post("/tracks", response_model=VisionTrackRead, status_code=201)
def create_track(payload: VisionTrackCreate, db: Session = Depends(get_db)) -> VisionTrackModel:
    if db.get(OrganizationModel, payload.organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    video = db.get(VideoModel, payload.video_id)
    if video is None or video.organization_id != payload.organization_id:
        raise HTTPException(status_code=404, detail="Video not found for organization")
    if payload.athlete_id and db.get(AthleteModel, payload.athlete_id) is None:
        raise HTTPException(status_code=404, detail="Athlete not found")
    track = VisionTrackModel(**payload.model_dump())
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


@router.post("/manual-selections", response_model=VisionManualSelectionRead)
def create_manual_selection(payload: VisionManualSelection, db: Session = Depends(get_db)) -> VisionManualSelectionRead:
    video = db.get(VideoModel, payload.video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if payload.athlete_id and db.get(AthleteModel, payload.athlete_id) is None:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return VisionManualSelectionRead(
        status="queued_for_segmentation",
        message="Manual selection captured. SAM3 segmentation is an assistive layer and is not running behavior detection.",
        video_id=payload.video_id,
        athlete_id=payload.athlete_id,
        frame_number=payload.frame_number,
        prompt=payload.prompt,
    )

