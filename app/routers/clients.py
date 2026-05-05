from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.database import get_db
from core.security import verify_dual_auth

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/by-phone/{phone}")
def get_client_by_phone(phone: str, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT id, name, email, phone, objective, status, created_at FROM clients WHERE phone = :p LIMIT 1"),
        {"p": phone}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return {"id": row[0], "name": row[1], "email": row[2], "phone": row[3], "objective": row[4], "status": row[5], "created_at": str(row[6])}


@router.get("/by-phone/{phone}/data")
def get_client_data(phone: str, db: Session = Depends(get_db)):
    client = db.execute(
        text("SELECT id, name, email, phone, objective, status FROM clients WHERE phone = :p LIMIT 1"),
        {"p": phone}
    ).fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    ob = db.execute(
        text("SELECT nome, objetivo, nivel_treino, dias_treino, meta_principal FROM lead_onboardings WHERE phone = :p ORDER BY created_at DESC LIMIT 1"),
        {"p": phone}
    ).fetchone()
    plan = db.execute(
        text("SELECT id, content, created_at FROM plan_versions WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
        {"cid": client[0]}
    ).fetchone()
    diet = db.execute(
        text("SELECT id, content, created_at FROM diet_versions WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
        {"cid": client[0]}
    ).fetchone()
    return {
        "client": {"id": client[0], "name": client[1], "email": client[2], "phone": client[3], "objective": client[4], "status": client[5]},
        "onboarding": {"nome": ob[0], "objetivo": ob[1], "nivel_treino": ob[2], "dias_treino": ob[3], "meta_principal": ob[4]} if ob else None,
        "plan": {"id": plan[0], "content": plan[1], "created_at": str(plan[2])} if plan else None,
        "diet": {"id": diet[0], "content": diet[1], "created_at": str(diet[2])} if diet else None,
    }


@router.get("")
def list_clients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    from models.client import Client
    if auth_client_id == 0:
        return db.query(Client).offset(skip).limit(min(limit, 500)).all()
    client = db.query(Client).filter(Client.id == auth_client_id).first()
    return [client] if client else []


@router.get("/{client_id}")
def get_client(client_id: int, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    from models.client import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return client


@router.patch("/{client_id}")
def update_client(client_id: int, payload: dict, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    from models.client import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    for field, value in payload.items():
        if hasattr(client, field):
            setattr(client, field, value)
    db.commit()
    return client


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin")
    from models.client import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    db.delete(client)
    db.commit()
    return None