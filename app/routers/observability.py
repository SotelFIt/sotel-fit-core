from fastapi import APIRouter, Depends
from core.observability import observability
from core.security import verify_jwt_only

router = APIRouter(prefix="/observability", tags=["observability"])

@router.get("/health/detailed")
async def get_health_detailed(client_id: int = Depends(verify_jwt_only)):
    try:
        return observability.get_health_detailed()
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

@router.get("/metrics")
async def get_metrics(client_id: int = Depends(verify_jwt_only)):
    try:
        return observability.get_metrics()
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}