from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import verify_dual_auth
from services.subscription_service import can_access_client_content

router = APIRouter(prefix="/diets", tags=["diets"])


def check_subscription(client_id: int, auth_client_id: int, db):
    if auth_client_id != 0:
        if not can_access_client_content(db, client_id):
            raise HTTPException(status_code=403, detail="Seu plano esta vencido. Renove para continuar acessando.")


@router.get("/client/{client_id}")
def get_client_diet(client_id: int, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        if auth_client_id != 0 and auth_client_id != client_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
        check_subscription(client_id, auth_client_id, db)
        from services.diet_service import get_diet_by_client
        return get_diet_by_client(db, client_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/client/{client_id}")
def create_client_diet(client_id: int, payload: dict, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        if auth_client_id != 0:
            raise HTTPException(status_code=403, detail="Apenas admin pode criar dieta")
        from services.diet_service import create_diet
        result = create_diet(db, client_id, payload)
        db.commit()
        return result
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))