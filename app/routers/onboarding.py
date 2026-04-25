from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from schemas.onboarding import OnboardingCreate, OnboardingResponse
from services.onboarding_service import (
    create_onboarding,
    get_all_onboarding,
    get_onboarding_by_client_id,
)
from database import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/onboarding", response_model=list[OnboardingResponse])
def list_onboarding(db: Session = Depends(get_db)):
    try:
        return get_all_onboarding(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/clients/{client_id}/onboarding", response_model=list[OnboardingResponse])
def list_client_onboarding(client_id: int, db: Session = Depends(get_db)):
    try:
        return get_onboarding_by_client_id(db, client_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/onboarding", response_model=OnboardingResponse)
def create_new_onboarding(onboarding: OnboardingCreate, db: Session = Depends(get_db)):
    try:
        result = create_onboarding(db, onboarding)
        db.commit()  # ✅ COMMIT aqui, no router
        db.refresh(result)
        return result
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao criar onboarding")