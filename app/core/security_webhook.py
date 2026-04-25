import os
from fastapi import HTTPException, status, Header
from typing import Optional

LANDBOT_SECRET_TOKEN = os.getenv("LANDBOT_SECRET_TOKEN")
if not LANDBOT_SECRET_TOKEN:
    raise RuntimeError("LANDBOT_SECRET_TOKEN não configurada.")

def verify_landbot_token(x_api_key: Optional[str] = Header(None)) -> str:
    """Valida x-api-key do webhook Landbot."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-api-key header"
        )
    
    if x_api_key != LANDBOT_SECRET_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return x_api_key
