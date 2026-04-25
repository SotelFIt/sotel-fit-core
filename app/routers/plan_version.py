from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import SessionLocal
from schemas.plan_version import PlanVersionListResponse
from services.plan_version_service import (
    list_plan_versions_by_plan,
    list_plan_versions_by_client,
)

router = APIRouter(tags=["plan_versions"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/plans/{plan_id}/versions", response_model=PlanVersionListResponse)
def get_plan_versions(plan_id: int, db: Session = Depends(get_db)):
    items = list_plan_versions_by_plan(db, plan_id)
    return {"items": items}


@router.get("/clients/{client_id}/plan-versions", response_model=PlanVersionListResponse)
def get_client_plan_versions(client_id: int, db: Session = Depends(get_db)):
    items = list_plan_versions_by_client(db, client_id)
    return {"items": items}