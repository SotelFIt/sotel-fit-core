"""
Clients Router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from core.database import get_db
from core.security import verify_dual_auth
from services.client_service import get_or_create_client_from_phone, normalize_phone

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/by-phone/{phone}")
def get_client_by_phone(phone: str, db: Session = Depends(get_db)):
    """
    Busca cliente por telefone.
    Fluxo:
    1. Normaliza telefone
    2. Busca em clients
    3. Se não encontrar, busca em conversation_states e cria o client
    4. Se não encontrar em nenhum, retorna 404
    """
    normalized = normalize_phone(phone)

    # 1. Buscar em clients
    row = db.execute(
        text("SELECT id, name, email, phone, objective, status, created_at FROM clients WHERE phone = :p LIMIT 1"),
        {"p": normalized}
    ).fetchone()

    if row:
        return {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "phone": row[3],
            "objective": row[4],
            "status": row[5],
            "created_at": str(row[6]),
        }

    # 2. Fallback: buscar em conversation_states e criar client automaticamente
    cs = db.execute(
        text("SELECT phone, name FROM conversation_states WHERE phone = :p LIMIT 1"),
        {"p": normalized}
    ).fetchone()

    if cs:
        client = get_or_create_client_from_phone(db, cs[0], cs[1])
        return {
            "id": client["id"],
            "name": client["name"],
            "email": None,
            "phone": client["phone"],
            "objective": client["objective"],
            "status": client["status"],
            "created_at": None,
        }

    raise HTTPException(status_code=404, detail="Cliente nao encontrado")


@router.get("/by-phone/{phone}/data")
def get_client_data(phone: str, db: Session = Depends(get_db)):
    """Retorna dados completos do cliente: perfil + onboarding + plano + dieta"""
    normalized = normalize_phone(phone)

    # Buscar client (com fallback)
    client = db.execute(
        text("SELECT id, name, email, phone, objective, status FROM clients WHERE phone = :p LIMIT 1"),
        {"p": normalized}
    ).fetchone()

    if not client:
        cs = db.execute(
            text("SELECT phone, name FROM conversation_states WHERE phone = :p LIMIT 1"),
            {"p": normalized}
        ).fetchone()
        if cs:
            created = get_or_create_client_from_phone(db, cs[0], cs[1])
            client_id = created["id"]
            client_info = created
        else:
            raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    else:
        client_id = client[0]
        client_info = {
            "id": client[0],
            "name": client[1],
            "email": client[2],
            "phone": client[3],
            "objective": client[4],
            "status": client[5],
        }

    # Buscar onboarding
    ob = db.execute(
        text("SELECT nome, objetivo, nivel_treino, dias_treino, meta_principal FROM lead_onboardings WHERE phone = :p ORDER BY created_at DESC LIMIT 1"),
        {"p": normalized}
    ).fetchone()

    # Buscar plano ativo
    plan = None
    try:
        plan = db.execute(
            text("SELECT id, content, created_at FROM plan_versions WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
            {"cid": client_id}
        ).fetchone()
    except Exception:
        pass

    # Buscar dieta ativa
    diet = None
    try:
        diet = db.execute(
            text("SELECT id, content, created_at FROM diet_versions WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
            {"cid": client_id}
        ).fetchone()
    except Exception:
        pass

    return {
        "client": client_info,
        "onboarding": {
            "nome": ob[0],
            "objetivo": ob[1],
            "nivel_treino": ob[2],
            "dias_treino": ob[3],
            "meta_principal": ob[4],
        } if ob else None,
        "plan": {"id": plan[0], "content": plan[1], "created_at": str(plan[2])} if plan else None,
        "diet": {"id": diet[0], "content": diet[1], "created_at": str(diet[2])} if diet else None,
    }


@router.get("")
def list_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    from models.client import Client
    if auth_client_id == 0:
        return db.query(Client).offset(skip).limit(min(limit, 500)).all()
    client = db.query(Client).filter(Client.id == auth_client_id).first()
    return [client] if client else []


@router.get("/{client_id}")
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    row = db.execute(
        text("SELECT id, name, email, phone, objective, status FROM clients WHERE id = :cid LIMIT 1"),
        {"cid": client_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return {"id": row[0], "name": row[1], "email": row[2], "phone": row[3], "objective": row[4], "status": row[5]}


@router.patch("/{client_id}")
def update_client(
    client_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    allowed = {"name", "email", "objective", "status"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="Nenhum campo valido para atualizar")
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["cid"] = client_id
    db.execute(text(f"UPDATE clients SET {set_clause} WHERE id = :cid"), updates)
    db.commit()
    return {"id": client_id, **{k: v for k, v in updates.items() if k != "cid"}}


@router.delete("/{client_id}", status_code=204)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin")
    db.execute(text("DELETE FROM clients WHERE id = :cid"), {"cid": client_id})
    db.commit()
    return None
