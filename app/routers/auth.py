"""
Auth Router
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from core.database import get_db
from core.security import (
    verify_refresh_token,
    create_token_pair,
    verify_dual_auth,
    TokenResponse,
)
from models.client import Client

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
    client = db.query(Client).filter(Client.id == auth_client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return client

@router.post("/login", status_code=200)
def login(payload: dict, db: Session = Depends(get_db)):
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email obrigatorio")
    client = db.query(Client).filter(Client.email == email).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    tokens = create_token_pair(client.id)
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
        "client": {
            "id": client.id,
            "name": client.name,
            "email": client.email,
            "objective": client.objective,
            "is_active": client.is_active,
        }
    }