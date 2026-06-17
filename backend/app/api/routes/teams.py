from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import OrganizationModel, TeamModel
from app.schemas import TeamCreate, TeamRead


router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[TeamRead])
def list_teams(
    organization_id: str | None = Query(default=None),
    sport: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[TeamModel]:
    statement = select(TeamModel)
    if organization_id:
        statement = statement.where(TeamModel.organization_id == organization_id)
    if sport:
        statement = statement.where(TeamModel.sport == sport)
    return list(db.scalars(statement.order_by(TeamModel.created_at.desc())))


@router.post("", response_model=TeamRead, status_code=201)
def create_team(payload: TeamCreate, db: Session = Depends(get_db)) -> TeamModel:
    if db.get(OrganizationModel, payload.organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    team = TeamModel(**payload.model_dump())
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/{team_id}", response_model=TeamRead)
def get_team(team_id: str, db: Session = Depends(get_db)) -> TeamModel:
    team = db.get(TeamModel, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team

