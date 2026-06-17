from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import CategoryModel, OrganizationModel, TagModel
from app.schemas import CategoryCreate, CategoryRead, TagCreate, TagRead


router = APIRouter(tags=["taxonomy"])


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(
    organization_id: str | None = Query(default=None),
    sport: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[CategoryModel]:
    statement = select(CategoryModel)
    if organization_id:
        statement = statement.where(CategoryModel.organization_id == organization_id)
    if sport:
        statement = statement.where(CategoryModel.sport == sport)
    return list(db.scalars(statement.order_by(CategoryModel.name.asc())))


@router.post("/categories", response_model=CategoryRead, status_code=201)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)) -> CategoryModel:
    if db.get(OrganizationModel, payload.organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    category = CategoryModel(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/tags", response_model=list[TagRead])
def list_tags(
    category_id: str | None = Query(default=None),
    organization_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[TagModel]:
    statement = select(TagModel).join(TagModel.category)
    if category_id:
        statement = statement.where(TagModel.category_id == category_id)
    if organization_id:
        statement = statement.where(CategoryModel.organization_id == organization_id)
    return list(db.scalars(statement.order_by(TagModel.name.asc())))


@router.post("/tags", response_model=TagRead, status_code=201)
def create_tag(payload: TagCreate, db: Session = Depends(get_db)) -> TagModel:
    if db.get(CategoryModel, payload.category_id) is None:
        raise HTTPException(status_code=404, detail="Category not found")
    tag = TagModel(**payload.model_dump())
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag

