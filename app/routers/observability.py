from fastapi import APIRouter, Header, HTTPException, status
from core.observability import observability
from core.security import verify_jwt_only
from typing import Optional

router = APIRouter(prefix="/observability", tags=["observability"])

@router.get("/health/detailed")
async def get_health_detailed(authorization: Optional[str] = Header(None)):
    try:
        verify_jwt_only(authorization=authorization)
        return observability.get_health_detailed()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

@router.get("/metrics")
async def get_metrics(authorization: Optional[str] = Header(None)):
    try:
        verify_jwt_only(authorization=authorization)
        return observability.get_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")
