from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import EventModel, TeamModel
from app.schemas import EventCreate, EventRead


router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventRead])
def list_events(
    organization_id: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[EventModel]:
    statement = select(EventModel)
    if organization_id:
        statement = statement.where(EventModel.organization_id == organization_id)
    if team_id:
        statement = statement.where(EventModel.team_id == team_id)
    return list(db.scalars(statement.order_by(EventModel.event_date.desc().nullslast(), EventModel.created_at.desc())))


@router.post("", response_model=EventRead, status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db)) -> EventModel:
    team = db.get(TeamModel, payload.team_id)
    if team is None or team.organization_id != payload.organization_id:
        raise HTTPException(status_code=404, detail="Team not found for organization")
    event = EventModel(**payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/{event_id}", response_model=EventRead)
def get_event(event_id: str, db: Session = Depends(get_db)) -> EventModel:
    event = db.get(EventModel, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

