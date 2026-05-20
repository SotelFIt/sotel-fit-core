from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from main import limiter
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.database import get_db
from core.security import (
    verify_refresh_token,
    create_token_pair,
    verify_dual_auth,
    TokenResponse,
)
import logging

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