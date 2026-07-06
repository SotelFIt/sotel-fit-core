from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.database import get_db
from core.security import (
    verify_refresh_token,
    create_token_pair,
    verify_dual_auth,
    create_magic_token,
    verify_magic_token,
    TokenResponse,
)
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/refresh", response_model=TokenResponse, status_code=200)
def refresh_token(client_id: int = Depends(verify_refresh_token)):
    return create_token_pair(client_id)


@router.post("/verify", status_code=200)
def verify_token_endpoint(auth_client_id: int = Depends(verify_dual_auth)):
    role = "admin" if auth_client_id == 0 else "client"
    return {"client_id": auth_client_id, "valid": True, "role": role}


@router.get("/me", status_code=200)
def get_current_user(db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    if auth_client_id == 0:
        return {"message": "Admin user"}
    row = db.execute(
        text("SELECT id, name, email, phone, objective, status FROM clients WHERE id = :cid LIMIT 1"),
        {"cid": auth_client_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return {"id": row[0], "name": row[1], "email": row[2], "phone": row[3], "objective": row[4], "status": row[5]}


@router.post("/login", status_code=200)
@limiter.limit("10/minute")
def login(request: Request, payload: dict, db: Session = Depends(get_db)):
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email obrigatorio")

    # Rate limit manual: max 10 tentativas por minuto por IP
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"Login attempt from {client_ip} for email={email}")

    row = db.execute(
        text("SELECT id, name, email, objective FROM clients WHERE email = :email LIMIT 1"),
        {"email": email}
    ).fetchone()
    if not row:
        logger.warning(f"Login failed: email nao encontrado {email} from {client_ip}")
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")

    tokens = create_token_pair(row[0])
    logger.info(f"Login sucesso: client_id={row[0]} email={email}")
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
        "client": {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "objective": row[3],
            "is_active": True,
        }
    }


CLIENT_APP_URL = os.getenv("CLIENT_APP_URL", "https://sotel-client.vercel.app")


@router.post("/magic-link/{client_id}", status_code=200)
def create_magic_link(client_id: int, auth_client_id: int = Depends(verify_dual_auth)):
    # Apenas admin (verify_dual_auth retorna 0 para admin).
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin")
    token = create_magic_token(client_id)
    return {"url": f"{CLIENT_APP_URL}/acesso#t={token}", "token": token}


@router.post("/magic-link/exchange", status_code=200)
@limiter.limit("20/minute")
def exchange_magic_link(request: Request, payload: dict, db: Session = Depends(get_db)):
    token = payload.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="token obrigatorio")
    try:
        client_id = verify_magic_token(token)  # assinatura + type=='magic' + expiracao
    except HTTPException:
        raise HTTPException(status_code=401, detail="Link invalido ou expirado")
    row = db.execute(
        text("SELECT id, name, email, objective FROM clients WHERE id = :cid LIMIT 1"),
        {"cid": client_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    tokens = create_token_pair(row[0])
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
        "client": {"id": row[0], "name": row[1], "email": row[2], "objective": row[3], "is_active": True},
    }


@router.post("/stripe-session", status_code=200)
def auth_stripe_session(payload: dict, db: Session = Depends(get_db)):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id obrigatorio")
    import stripe
    import os
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="session_id invalido")
    customer_details = session.get("customer_details") or {}
    email = customer_details.get("email") or session.get("customer_email")
    phone = customer_details.get("phone")
    row = None
    if email:
        row = db.execute(
            text("SELECT id, name, email, phone, objective FROM clients WHERE email = :e LIMIT 1"),
            {"e": email}
        ).fetchone()
    if not row and phone:
        from core.phone import normalize_phone
        phone_norm = normalize_phone(phone)
        row = db.execute(
            text("SELECT id, name, email, phone, objective FROM clients WHERE phone = :p LIMIT 1"),
            {"p": phone_norm}
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    tokens = create_token_pair(row[0])
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
        "onboarding_required": True,
        "client": {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "phone": row[3],
            "objective": row[4],
        }
    }