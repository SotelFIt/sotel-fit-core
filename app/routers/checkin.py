from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import verify_dual_auth
from schemas.checkin import CheckinCreate, CheckinResponse
from services.checkin_service import create_checkin, get_checkins_by_client, analyze_checkin, apply_checkin_decision
from services.subscription_service import can_access_client_content

router = APIRouter(prefix="/checkins", tags=["checkins"])


def check_checkin_access(client_id: int, auth_client_id: int):
    if auth_client_id != 0 and auth_client_id != client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")


def check_subscription(client_id: int, auth_client_id: int, db):
    if auth_client_id != 0:
        if not can_access_client_content(db, client_id):
            raise HTTPException(status_code=403, detail="Seu plano esta vencido. Renove para continuar acessando.")


@router.post("", response_model=CheckinResponse, status_code=status.HTTP_201_CREATED)
def create_new_checkin(checkin: CheckinCreate, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        if auth_client_id != 0 and auth_client_id != checkin.client_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
        check_subscription(checkin.client_id, auth_client_id, db)
        result = create_checkin(db, checkin)
        db.commit()
        db.refresh(result)
        return result
    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao criar check-in")


@router.get("/client/{client_id}", response_model=List[CheckinResponse])
def list_checkins(client_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        check_checkin_access(client_id, auth_client_id)
        check_subscription(client_id, auth_client_id, db)
        return get_checkins_by_client(db, client_id, skip, limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client/{client_id}/analysis")
def get_checkin_analysis(client_id: int, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        check_checkin_access(client_id, auth_client_id)
        check_subscription(client_id, auth_client_id, db)
        return analyze_checkin(db, client_id)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erro ao analisar check-in")


@router.post("/client/{client_id}/apply-decision")
def apply_decision(client_id: int, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        check_checkin_access(client_id, auth_client_id)
        result = apply_checkin_decision(db, client_id)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao aplicar decisao")