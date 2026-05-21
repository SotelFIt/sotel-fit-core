from fastapi import APIRouter
from core.observability import observability

router = APIRouter(prefix="/observability", tags=["observability"])

@router.get("/health/detailed")
async def get_health_detailed():
    try:
        return observability.get_health_detailed()
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

@router.get("/metrics")
async def get_metrics():
    try:
        return observability.get_metrics()
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}