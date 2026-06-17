from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.routes.evidence import _evidence_detail
from app.models import AthleteModel, EvidenceTagModel, NoteModel, TeamModel
from app.schemas import AthleteCreate, AthleteProfile, AthleteRead, BehaviorFrequency, NoteRead


router = APIRouter(prefix="/athletes", tags=["athletes"])


@router.get("", response_model=list[AthleteRead])
def list_athletes(
    organization_id: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[AthleteModel]:
    statement = select(AthleteModel)
    if organization_id:
        statement = statement.where(AthleteModel.organization_id == organization_id)
    if team_id:
        statement = statement.where(AthleteModel.team_id == team_id)
    return list(db.scalars(statement.order_by(AthleteModel.display_name.asc())))


@router.post("", response_model=AthleteRead, status_code=201)
def create_athlete(payload: AthleteCreate, db: Session = Depends(get_db)) -> AthleteModel:
    team = db.get(TeamModel, payload.team_id)
    if team is None or team.organization_id != payload.organization_id:
        raise HTTPException(status_code=404, detail="Team not found for organization")
    athlete = AthleteModel(**payload.model_dump())
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete


@router.get("/{athlete_id}", response_model=AthleteRead)
def get_athlete(athlete_id: str, db: Session = Depends(get_db)) -> AthleteModel:
    athlete = db.get(AthleteModel, athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return athlete


@router.get("/{athlete_id}/profile", response_model=AthleteProfile)
def get_athlete_profile(athlete_id: str, db: Session = Depends(get_db)) -> AthleteProfile:
    athlete = db.get(AthleteModel, athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="Athlete not found")

    evidence_entries = list(
        db.scalars(
            select(EvidenceTagModel)
            .where(EvidenceTagModel.athlete_id == athlete_id)
            .order_by(EvidenceTagModel.created_at.desc())
        )
    )
    notes = list(
        db.scalars(select(NoteModel).where(NoteModel.athlete_id == athlete_id).order_by(NoteModel.created_at.desc()))
    )

    all_frequency = _behavior_frequency(evidence_entries)
    strengths = _behavior_frequency([entry for entry in evidence_entries if entry.evidence_type == "strength"])
    development = _behavior_frequency(
        [entry for entry in evidence_entries if entry.evidence_type == "development_area"]
    )

    consistency = sorted(
        all_frequency,
        key=lambda item: (item.event_count, item.video_count, item.evidence_count),
        reverse=True,
    )

    return AthleteProfile(
        athlete=AthleteRead.model_validate(athlete),
        strengths=strengths,
        development_areas=development,
        behavior_frequency=all_frequency,
        behavior_consistency=consistency,
        evidence_clips=[_evidence_detail(entry) for entry in evidence_entries],
        coach_notes=[NoteRead.model_validate(note) for note in notes],
    )


@dataclass
class _BehaviorBucket:
    category_id: str
    category_name: str
    tag_id: str
    tag_name: str
    evidence_count: int = 0
    video_ids: set[str] = field(default_factory=set)
    event_ids: set[str] = field(default_factory=set)
    latest_timestamp_seconds: float | None = None


def _behavior_frequency(entries: list[EvidenceTagModel]) -> list[BehaviorFrequency]:
    buckets: dict[tuple[str, str], _BehaviorBucket] = {}
    for entry in entries:
        key = (entry.category_id, entry.tag_id)
        if key not in buckets:
            buckets[key] = _BehaviorBucket(
                category_id=entry.category_id,
                category_name=entry.category.name,
                tag_id=entry.tag_id,
                tag_name=entry.tag.name,
            )
        bucket = buckets[key]
        bucket.evidence_count += 1
        bucket.video_ids.add(entry.video_id)
        if entry.event_id:
            bucket.event_ids.add(entry.event_id)
        if bucket.latest_timestamp_seconds is None:
            bucket.latest_timestamp_seconds = entry.timestamp_seconds

    return sorted(
        [
            BehaviorFrequency(
                category_id=bucket.category_id,
                category_name=bucket.category_name,
                tag_id=bucket.tag_id,
                tag_name=bucket.tag_name,
                evidence_count=bucket.evidence_count,
                video_count=len(bucket.video_ids),
                event_count=len(bucket.event_ids),
                latest_timestamp_seconds=bucket.latest_timestamp_seconds,
            )
            for bucket in buckets.values()
        ],
        key=lambda item: item.evidence_count,
        reverse=True,
    )

