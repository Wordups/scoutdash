from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import (
    AthleteModel,
    CategoryModel,
    ClipModel,
    EvidenceTagModel,
    TagModel,
    TeamModel,
    VideoModel,
)
from app.schemas import ClipRead, EvidenceTagCreate, EvidenceTagDetail, EvidenceTagRead


router = APIRouter(prefix="/evidence-tags", tags=["evidence"])


@router.get("", response_model=list[EvidenceTagDetail])
def list_evidence_tags(
    organization_id: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    athlete_id: str | None = Query(default=None),
    video_id: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    tag_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[EvidenceTagDetail]:
    statement = select(EvidenceTagModel)
    if organization_id:
        statement = statement.where(EvidenceTagModel.organization_id == organization_id)
    if team_id:
        statement = statement.where(EvidenceTagModel.team_id == team_id)
    if athlete_id:
        statement = statement.where(EvidenceTagModel.athlete_id == athlete_id)
    if video_id:
        statement = statement.where(EvidenceTagModel.video_id == video_id)
    if category_id:
        statement = statement.where(EvidenceTagModel.category_id == category_id)
    if tag_id:
        statement = statement.where(EvidenceTagModel.tag_id == tag_id)

    entries = list(db.scalars(statement.order_by(EvidenceTagModel.created_at.desc())))
    return [_evidence_detail(entry) for entry in entries]


@router.post("", response_model=EvidenceTagRead, status_code=201)
def create_evidence_tag(payload: EvidenceTagCreate, db: Session = Depends(get_db)) -> EvidenceTagModel:
    athlete = db.get(AthleteModel, payload.athlete_id)
    team = db.get(TeamModel, payload.team_id)
    video = db.get(VideoModel, payload.video_id)
    category = db.get(CategoryModel, payload.category_id)
    tag = db.get(TagModel, payload.tag_id)

    if team is None or team.organization_id != payload.organization_id:
        raise HTTPException(status_code=404, detail="Team not found for organization")
    if athlete is None or athlete.team_id != payload.team_id:
        raise HTTPException(status_code=404, detail="Athlete not found for team")
    if video is None or video.team_id != payload.team_id:
        raise HTTPException(status_code=404, detail="Video not found for team")
    if category is None or category.organization_id != payload.organization_id:
        raise HTTPException(status_code=404, detail="Category not found for organization")
    if tag is None or tag.category_id != payload.category_id:
        raise HTTPException(status_code=404, detail="Tag not found for category")

    start = payload.clip_start_seconds
    end = payload.clip_end_seconds
    if start is None or end is None:
        start = max(payload.timestamp_seconds - 4, 0)
        end = payload.timestamp_seconds + 4

    clip = ClipModel(
        organization_id=payload.organization_id,
        team_id=payload.team_id,
        event_id=payload.event_id or video.event_id,
        video_id=payload.video_id,
        title=f"{category.name}: {tag.name}",
        start_time_seconds=start,
        end_time_seconds=end,
        notes=payload.notes,
    )
    db.add(clip)
    db.flush()

    evidence = EvidenceTagModel(
        organization_id=payload.organization_id,
        team_id=payload.team_id,
        athlete_id=payload.athlete_id,
        event_id=payload.event_id or video.event_id,
        video_id=payload.video_id,
        clip_id=clip.id,
        category_id=payload.category_id,
        tag_id=payload.tag_id,
        timestamp_seconds=payload.timestamp_seconds,
        evidence_type=payload.evidence_type,
        notes=payload.notes,
        created_by=payload.created_by,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def _evidence_detail(entry: EvidenceTagModel) -> EvidenceTagDetail:
    return EvidenceTagDetail(
        id=entry.id,
        organization_id=entry.organization_id,
        team_id=entry.team_id,
        athlete_id=entry.athlete_id,
        event_id=entry.event_id,
        video_id=entry.video_id,
        clip_id=entry.clip_id,
        category_id=entry.category_id,
        tag_id=entry.tag_id,
        timestamp_seconds=entry.timestamp_seconds,
        evidence_type=entry.evidence_type,
        notes=entry.notes,
        created_by=entry.created_by,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        athlete_name=entry.athlete.display_name,
        category_name=entry.category.name,
        tag_name=entry.tag.name,
        video_title=entry.video.title,
        clip=ClipRead.model_validate(entry.clip) if entry.clip else None,
    )

