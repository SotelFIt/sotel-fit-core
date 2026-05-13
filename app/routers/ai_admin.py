import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from routers.admin import require_admin
from services.ai_operator_service import analyze_client, analyze_all_clients

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-admin", tags=["ai-admin"])


@router.get("/clients/{client_id}/analysis")
def get_client_analysis(
    client_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    """Análise de risco individual de um cliente (somente leitura)."""
    result = analyze_client(db, client_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/clients/at-risk")
def get_clients_at_risk(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    """Lista todos os clientes ordenados por score de risco (somente leitura)."""
    return analyze_all_clients(db)


@router.get("/summary")
def get_operational_summary(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    """Resumo operacional geral com contagem por nível de risco."""
    data = analyze_all_clients(db)
    return {
        "summary": {
            "total_clients": data["total_clients"],
            "high_risk_count": data["high_risk_count"],
            "medium_risk_count": data["medium_risk_count"],
            "low_risk_count": data["low_risk_count"],
        },
        "high_risk_clients": [
            c for c in data["clients_by_risk"] if c["risk_level"] == "alto"
        ],
        "analyzed_at": data["analyzed_at"],
    }
