from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from core.database import engine

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/cleanup-status")
async def audit_cleanup_status():
    """Auditoria geral do banco"""
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

@router.get("/leads-detail")
async def audit_leads_detail():
    """Lista detalhada de todos os leads em produção"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, phone, nome, email, idade, peso, altura, objetivo, 
                       nivel_treino, created_at 
                FROM lead_onboardings 
                ORDER BY created_at DESC
                LIMIT 20
            """))
            
            leads = []
            for row in result:
                leads.append({
                    "id": row[0],
                    "phone": row[1],
                    "name": row[2],
                    "email": row[3],
                    "age": row[4],
                    "weight": row[5],
                    "height": row[6],
                    "goal": row[7],
                    "training_level": row[8],
                    "created_at": str(row[9]) if row[9] else None
                })
            
            return {
                "status": "ok",
                "total_leads": len(leads),
                "leads": leads
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/data-integrity")
async def audit_data_integrity():
    """Verifica integridade dos dados"""
    try:
        with engine.connect() as conn:
            integrity = {}
            
            # Clientes sem subscriptions
            orphan_clients = conn.execute(text("""
                SELECT COUNT(*) FROM clients c 
                WHERE NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.client_id = c.id)
            """)).scalar()
            integrity["clients_without_subscription"] = orphan_clients
            
            # Timeline events órfãos
            orphan_timeline = conn.execute(text("""
                SELECT COUNT(*) FROM timeline_events t 
                WHERE NOT EXISTS (SELECT 1 FROM clients c WHERE c.id = t.client_id)
            """)).scalar()
            integrity["orphan_timeline_events"] = orphan_timeline
            
            # Check-ins órfãos
            orphan_checkins = conn.execute(text("""
                SELECT COUNT(*) FROM checkins ch 
                WHERE NOT EXISTS (SELECT 1 FROM clients c WHERE c.id = ch.client_id)
            """)).scalar()
            integrity["orphan_checkins"] = orphan_checkins
            
            return {
                "status": "ok",
                "integrity": integrity,
                "issues_found": orphan_clients > 0 or orphan_timeline > 0 or orphan_checkins > 0
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))