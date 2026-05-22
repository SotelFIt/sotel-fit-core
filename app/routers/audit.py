from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from core.database import engine, get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/cleanup-status")
async def audit_cleanup_status():
    """Auditoria de limpeza do banco — retorna contagem de registros"""
    try:
        with engine.connect() as conn:
            stats = {}
            
            tables = [
                "clients", "checkins", "subscriptions", "plans", "diets",
                "client_plans", "client_diets", "client_checkins",
                "lead_onboardings", "onboarding", "timeline_events",
                "achievements", "decision_logs", "conversation_states"
            ]
            
            for table in tables:
                try:
                    total = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    stats[table] = total
                except:
                    stats[table] = "N/A"
            
            return {
                "status": "ok",
                "environment": "production",
                "data": stats
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))