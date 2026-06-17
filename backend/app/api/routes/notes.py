from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import NoteModel, OrganizationModel
from app.schemas import NoteCreate, NoteRead


router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=list[NoteRead])
def list_notes(
    organization_id: str | None = Query(default=None),
    athlete_id: str | None = Query(default=None),
    video_id: str | None = Query(default=None),
    clip_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[NoteModel]:
    statement = select(NoteModel)
    if organization_id:
        statement = statement.where(NoteModel.organization_id == organization_id)
    if athlete_id:
        statement = statement.where(NoteModel.athlete_id == athlete_id)
    if video_id:
        statement = statement.where(NoteModel.video_id == video_id)
    if clip_id:
        statement = statement.where(NoteModel.clip_id == clip_id)
    return list(db.scalars(statement.order_by(NoteModel.created_at.desc())))


@router.post("", response_model=NoteRead, status_code=201)
def create_note(payload: NoteCreate, db: Session = Depends(get_db)) -> NoteModel:
    if db.get(OrganizationModel, payload.organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    note = NoteModel(**payload.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

