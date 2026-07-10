from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timedelta
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

import jwt
from fastapi import HTTPException, status, Header, Depends
from pydantic import BaseModel

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY nao configurada.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_HOURS", "24"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

LANDBOT_SECRET_TOKEN = os.getenv("LANDBOT_SECRET_TOKEN")
if not LANDBOT_SECRET_TOKEN:
    raise RuntimeError("LANDBOT_SECRET_TOKEN nao configurada.")

class TokenPayload(BaseModel):
    sub: int
    iat: int
    exp: int
    type: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

def create_access_token(client_id: int) -> str:
    now = datetime.utcnow()
    expire = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": client_id, "iat": int(now.timestamp()), "exp": int(expire.timestamp()), "type": "access"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(client_id: int) -> str:
    now = datetime.utcnow()
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": client_id, "iat": int(now.timestamp()), "exp": int(expire.timestamp()), "type": "refresh"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_token_pair(client_id: int) -> TokenResponse:
    access = create_access_token(client_id)
    refresh = create_refresh_token(client_id)
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600)

def create_magic_token(client_id: int) -> str:
    """Token de acesso identificado por cliente (Camada 2). type='magic', assinado, com expiracao."""
    now = datetime.utcnow()
    expire = now + timedelta(days=int(os.getenv("MAGIC_LINK_EXPIRE_DAYS", "7")))
    payload = {"sub": client_id, "iat": int(now.timestamp()), "exp": int(expire.timestamp()), "type": "magic"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_magic_token(token: str) -> int:
    """Valida assinatura + type=='magic' + expiracao. Reusa verify_token (que exige o type),
    logo um token 'magic' NUNCA passa como Bearer de dados (verify_dual_auth usa type='access')."""
    return verify_token(token, token_type="magic")

def verify_token(token: str, token_type: str = "access") -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_iat": False, "verify_sub": False})
        if payload.get("type") != token_type:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        client_id = payload.get("sub")
        if client_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return client_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def verify_dual_auth(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_access_token: Optional[str] = Header(None),
) -> int:
    # Tenta Bearer token via Authorization header
    if authorization:
        try:
            scheme, _, credentials = authorization.partition(" ")
            if scheme.lower() == "bearer":
                return verify_token(credentials, token_type="access")
        except HTTPException:
            pass

    # Tenta token via x-access-token header (alternativa para proxies)
    if x_access_token:
        try:
            return verify_token(x_access_token, token_type="access")
        except HTTPException:
            pass

    # Tenta API key
    if x_api_key:
        if x_api_key == LANDBOT_SECRET_TOKEN:
            return 0
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication")


def require_client_access(client_id: int, auth_client_id: int = Depends(verify_dual_auth)) -> int:
    """Autorização de POSSE para rotas /.../{client_id}: só o próprio cliente (JWT com
    sub==client_id) ou admin/Landbot (API key -> 0). Fecha IDOR sem duplicar lógica nem
    tocar o contrato (só acrescenta 401 sem auth / 403 para outro cliente)."""
    if auth_client_id != 0 and auth_client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")
    return auth_client_id


def require_admin(auth_client_id: int = Depends(verify_dual_auth)) -> int:
    """Somente admin/Landbot (API key -> 0). Para rotas sem client_id de posse (ex.:
    delete por event_id, lookup por telefone, debug)."""
    if auth_client_id != 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas admin")
    return auth_client_id


def verify_jwt_only(authorization: Optional[str] = Header(None)) -> int:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid scheme")
    return verify_token(credentials, token_type="access")

def verify_refresh_token(authorization: Optional[str] = Header(None)) -> int:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid scheme")
    return verify_token(credentials, token_type="refresh")