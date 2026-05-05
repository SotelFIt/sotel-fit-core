"""
Clients Router
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import verify_dual_auth
from models.client import Client
from models.lead_onboarding import LeadOnboarding

router = APIRouter(prefix="/clients", tags=["clients"])


def check_client_access(client_id: int, auth_client_id: int):
    if auth_client_id != 0 and auth_client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para acessar este cliente"
        )


@router.get("/by-phone/{phone}")
def get_client_by_phone(phone: str, db: Session = Depends(get_db)):
    """Busca cliente por telefone — usado para login simplificado"""
    client = db.query(Client).filter(Client.phone == phone).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return {
        "id": client.id,
        "name": client.name,
        "email": client.email,
        "phone": client.phone,
        "objective": client.objective,
        "status": client.status,
        "created_at": client.created_at,
    }


@router.get("/by-phone/{phone}/data")
def get_client_data(phone: str, db: Session = Depends(get_db)):
    """Retorna dados completos do cliente: perfil + onboarding + planos + dietas"""
    client = db.query(Client).filter(Client.phone == phone).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")

    # Buscar onboarding
    onboarding = db.query(LeadOnboarding).filter(
        LeadOnboarding.phone == phone
    ).order_by(LeadOnboarding.created_at.desc()).first()

    # Buscar plano ativo
    plan_data = None
    if client.current_plan:
        plan = client.current_plan
        plan_data = {
            "id": plan.id,
            "name": getattr(plan, "name", None),
            "type": getattr(plan, "type", None),
        }

    # Buscar versão ativa do plano
    active_plan_version = None
    if client.plan_versions:
        for pv in reversed(client.plan_versions):
            if getattr(pv, "status", None) == "active":
                active_plan_version = {
                    "id": pv.id,
                    "content": getattr(pv, "content", None),
                    "created_at": str(pv.created_at),
                }
                break

    # Buscar dieta ativa
    active_diet = None
    if client.diet_versions:
        for dv in reversed(client.diet_versions):
            if getattr(dv, "status", None) == "active":
                active_diet = {
                    "id": dv.id,
                    "content": getattr(dv, "content", None),
                    "created_at": str(dv.created_at),
                }
                break

    return {
        "client": {
            "id": client.id,
            "name": client.name,
            "email": client.email,
            "phone": client.phone,
            "objective": client.objective,
            "status": client.status,
        },
        "onboarding": {
            "nome": onboarding.nome,
            "objetivo": onboarding.objetivo,
            "nivel_treino": onboarding.nivel_treino,
            "dias_treino": onboarding.dias_treino,
            "meta_principal": onboarding.meta_principal,
        } if onboarding else None,
        "plan": active_plan_version,
        "diet": active_diet,
    }


@router.get("", status_code=status.HTTP_200_OK)
def list_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    if auth_client_id == 0:
        clients = db.query(Client).offset(skip).limit(min(limit, 500)).all()
    else:
        client = db.query(Client).filter(Client.id == auth_client_id).first()
        clients = [client] if client else []
    return clients


@router.get("/{client_id}", status_code=status.HTTP_200_OK)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    check_client_access(client_id, auth_client_id)
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


@router.patch("/{client_id}", status_code=status.HTTP_200_OK)
def update_client(
    client_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    check_client_access(client_id, auth_client_id)
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    for field, value in payload.items():
        if hasattr(client, field):
            setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin pode deletar clientes")
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    db.delete(client)
    db.commit()
    return None
