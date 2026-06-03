from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
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
@router.post("/onboarding/lead")
def create_onboarding_lead(payload: dict, db: Session = Depends(get_db)):
    try:
        from core.phone import normalize_phone

        email = payload.get("email")
        telefone = payload.get("telefone")
        phone_normalized = normalize_phone(telefone) if telefone else None

        client_row = None
        if email:
            client_row = db.execute(
                text("SELECT id FROM clients WHERE email = :e LIMIT 1"),
                {"e": email}
            ).fetchone()
        if not client_row and phone_normalized:
            client_row = db.execute(
                text("SELECT id FROM clients WHERE phone = :p LIMIT 1"),
                {"p": phone_normalized}
            ).fetchone()
        if not client_row:
            raise HTTPException(status_code=404, detail="Cliente nao encontrado")

        client_id = client_row[0]

        onboarding_data = OnboardingCreate(
            client_id=client_id,
            main_goal=payload.get("objetivo", ""),
            training_level=payload.get("nivel_treino", ""),
            injuries=payload.get("lesoes", ""),
            routine=payload.get("alimentacao_atual", ""),
            current_eating=payload.get("alimentacao_atual", ""),
            difficulties=payload.get("maior_dificuldade", ""),
            motivation=payload.get("observacoes", ""),
        )

        create_onboarding(db, onboarding_data)
        db.commit()

        return {"status": "ok", "client_id": client_id}
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))