"""
Landbot Webhook Router
Integração com Landbot (WhatsApp)
- Cria cliente com idempotência
- Retorna JWT (access + refresh token)
- Autenticação via x-api-key (token Landbot)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import (
    create_token_pair,
    TokenResponse,
    LANDBOT_SECRET_TOKEN
)
from schemas.landbot import LandbotRequestSchema, ClientResponseSchema
from services.landbot_service import create_client_idempotent
from models.client import Client

router = APIRouter(prefix="/webhook", tags=["webhook"])


# ============================================================================
# LANDBOT TOKEN VERIFICATION
# ============================================================================

def verify_landbot_token(x_api_key: Optional[str] = Header(None)) -> None:
    """
    Valida o token do Landbot via header x-api-key.
    Levanta HTTPException 401 se inválido ou ausente.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-api-key header. Provide Landbot secret token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if x_api_key != LANDBOT_SECRET_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid x-api-key. Token mismatch.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# SCHEMAS
# ============================================================================

class ClientWithTokenResponse(ClientResponseSchema):
    """Resposta: cliente + tokens JWT"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/landbot",
    response_model=ClientWithTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Webhook Landbot - Criar Cliente",
    description="Cria cliente via Landbot. Requer x-api-key (token Landbot). Retorna JWT tokens."
)
def webhook_landbot(
    payload: LandbotRequestSchema,
    db: Session = Depends(get_db),
    # Autenticação: exigir x-api-key (token Landbot)
    _: None = Depends(verify_landbot_token)
):
    """
    Webhook Landbot (WhatsApp)

    Autenticação:
    - Header: `x-api-key: <landbot_secret_token>` (OBRIGATÓRIO)

    Body:
```json
    {
      "landbot_user_id": "user123",
      "name": "João",
      "phone": "+5511999999999",
      "email": "joao@example.com",
      "objective": "Perder peso",
      "difficulty": "iniciante"
    }
```

    Response:
```json
    {
      "id": 1,
      "name": "João",
      "email": "joao@example.com",
      "phone": "+5511999999999",
      "objective": "Perder peso",
      "difficulty": "iniciante",
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "token_type": "bearer",
      "expires_in": 86400
    }
```

    Erros:
    - 401: x-api-key ausente ou inválido
    - 400: payload inválido
    - 409: cliente duplicado (mesmo landbot_user_id)
    """

    # Criar cliente ou retornar existente (idempotência)
    client = create_client_idempotent(
        db=db,
        landbot_user_id=payload.landbot_user_id,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        objective=payload.objective,
        difficulty=payload.difficulty
    )

    # Gerar JWT para o cliente
    token_pair = create_token_pair(client.id)

    # Montar resposta
    return ClientWithTokenResponse(
        id=client.id,
        name=client.name,
        email=client.email,
        phone=client.phone,
        objective=client.objective,
        difficulty=client.difficulty,
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
        expires_in=token_pair.expires_in
    )


@router.get(
    "/landbot/health",
    status_code=status.HTTP_200_OK,
    summary="Health Check - Webhook Landbot",
    description="Verifica se webhook está pronto. Sem autenticação (apenas status)."
)
def webhook_health():
    """Status do webhook - sem autenticação necessária"""
    return {
        "status": "ok",
        "message": "Landbot webhook is ready"
    }
