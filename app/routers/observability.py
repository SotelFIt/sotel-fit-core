from fastapi import APIRouter
from core.observability import observability

router = APIRouter(prefix="/observability", tags=["observability"])

@router.get("/health/detailed")
async def get_health_detailed():
    return observability.get_health_detailed()

@router.get("/metrics")
async def get_metrics():
    return observability.get_metrics()