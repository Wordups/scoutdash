from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import OrganizationModel
from app.schemas import OrganizationCreate, OrganizationRead


router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationRead])
def list_organizations(db: Session = Depends(get_db)) -> list[OrganizationModel]:
    return list(db.scalars(select(OrganizationModel).order_by(OrganizationModel.created_at.desc())))


@router.post("", response_model=OrganizationRead, status_code=201)
def create_organization(payload: OrganizationCreate, db: Session = Depends(get_db)) -> OrganizationModel:
    organization = OrganizationModel(**payload.model_dump())
    db.add(organization)
    db.commit()
    db.refresh(organization)
    return organization


@router.get("/{organization_id}", response_model=OrganizationRead)
def get_organization(organization_id: str, db: Session = Depends(get_db)) -> OrganizationModel:
    organization = db.get(OrganizationModel, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization

