from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import verify_dual_auth
from schemas.plan import PlanCreate, PlanResponse
from services.plan_service import create_plan, generate_automatic_plan, get_all_plans, get_plans_by_client_id, regenerate_plan
from services.subscription_service import can_access_client_content

router = APIRouter(tags=["plans"])


def check_subscription(client_id: int, auth_client_id: int, db):
    if auth_client_id != 0:
        if not can_access_client_content(db, client_id):
            raise HTTPException(status_code=403, detail="Seu plano esta vencido. Renove para continuar acessando.")


@router.get("/plans", response_model=list[PlanResponse])
def list_all_plans(db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        return get_all_plans(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clients/{client_id}/plans", response_model=list[PlanResponse])
def list_client_plans(client_id: int, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        check_subscription(client_id, auth_client_id, db)
        return get_plans_by_client_id(db, client_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plans", response_model=PlanResponse)
def create_new_plan(plan: PlanCreate, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        result = create_plan(db, plan)
        db.commit()
        db.refresh(result)
        return result
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao criar plano")


@router.post("/generate-plan/{client_id}", response_model=PlanResponse)
def generate_plan(client_id: int, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        result = generate_automatic_plan(db, client_id)
        db.commit()
        db.refresh(result)
        return result
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao gerar plano")


@router.post("/regenerate-plan/{client_id}", response_model=PlanResponse)
def regenerate_client_plan(client_id: int, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        result = regenerate_plan(db, client_id)
        db.commit()
        db.refresh(result)
        return result
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao regenerar plano")