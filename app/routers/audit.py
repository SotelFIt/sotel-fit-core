from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from core.database import engine

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/cleanup-status")
async def audit_cleanup_status():
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
            return {"status": "ok", "environment": "production", "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads-detail")
async def audit_leads_detail():
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
            return {"status": "ok", "total_leads": len(leads), "leads": leads}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data-integrity")
async def audit_data_integrity():
    try:
        with engine.connect() as conn:
            integrity = {}
            orphan_clients = conn.execute(text("""
                SELECT COUNT(*) FROM clients c
                WHERE NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.client_id = c.id)
            """)).scalar()
            integrity["clients_without_subscription"] = orphan_clients

            orphan_timeline = conn.execute(text("""
                SELECT COUNT(*) FROM timeline_events t
                WHERE NOT EXISTS (SELECT 1 FROM clients c WHERE c.id = t.client_id)
            """)).scalar()
            integrity["orphan_timeline_events"] = orphan_timeline

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


@router.get("/orphan-clients")
async def audit_orphan_clients():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT c.id, c.name, c.status, c.created_at
                FROM clients c
                WHERE NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.client_id = c.id)
                ORDER BY c.created_at DESC
                LIMIT 20
            """))
            clients = []
            for row in result:
                clients.append({
                    "id": row[0],
                    "name": row[1],
                    "status": row[2],
                    "created_at": str(row[3]) if row[3] else None
                })
            return {"status": "ok", "total_orphan_clients": len(clients), "clients": clients}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup-fake-data")
async def cleanup_fake_data():
    try:
        with engine.connect() as conn:
            deleted = {}
            result = conn.execute(text("DELETE FROM lead_onboardings WHERE id IN (3, 2)"))
            deleted["fake_leads"] = result.rowcount
            result = conn.execute(text("DELETE FROM clients WHERE id IN (2, 10, 14, 15)"))
            deleted["fake_clients"] = result.rowcount
            conn.commit()
            return {
                "status": "ok",
                "message": "Limpeza concluida com sucesso",
                "deleted": deleted
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate-client/{client_id}")
async def validate_client_detailed(client_id: int):
    try:
        with engine.connect() as conn:
            client_result = conn.execute(text("""
                SELECT id, name, phone, email, status, created_at, updated_at
                FROM clients
                WHERE id = :client_id
            """), {"client_id": client_id})
            client_row = client_result.fetchone()

            if not client_row:
                return {"status": "error", "message": f"Cliente {client_id} nao encontrado"}

            client_data = {
                "id": client_row[0],
                "name": client_row[1],
                "phone": client_row[2],
                "email": client_row[3],
                "status": client_row[4],
                "created_at": str(client_row[5]) if client_row[5] else None,
                "updated_at": str(client_row[6]) if client_row[6] else None
            }

            onboarding_result = conn.execute(text("""
                SELECT id, phone, nome, email, objetivo, nivel_treino, created_at
                FROM lead_onboardings
                WHERE phone = :phone
                LIMIT 5
            """), {"phone": client_data["phone"]})
            onboardings = []
            for row in onboarding_result:
                onboardings.append({
                    "id": row[0],
                    "phone": row[1],
                    "nome": row[2],
                    "email": row[3],
                    "objetivo": row[4],
                    "nivel_treino": row[5],
                    "created_at": str(row[6]) if row[6] else None
                })

            timeline_result = conn.execute(text("""
                SELECT id, event_type, description, created_at
                FROM timeline_events
                WHERE client_id = :client_id
                ORDER BY created_at DESC
                LIMIT 10
            """), {"client_id": client_id})
            timeline = []
            for row in timeline_result:
                timeline.append({
                    "id": row[0],
                    "event_type": row[1],
                    "description": row[2],
                    "created_at": str(row[3]) if row[3] else None
                })

           checkin_result = conn.execute(text("""
    SELECT id, created_at
    FROM client_checkins
    WHERE client_id = :client_id
    ORDER BY created_at DESC
    LIMIT 10
"""), {"client_id": client_id})
checkins = []
for row in checkin_result:
    checkins.append({
        "id": row[0],
        "created_at": str(row[1]) if row[1] else None
    })

            plan_result = conn.execute(text("""
                SELECT id, plan_type, status, created_at
                FROM client_plans
                WHERE client_id = :client_id
                LIMIT 5
            """), {"client_id": client_id})
            plans = []
            for row in plan_result:
                plans.append({
                    "id": row[0],
                    "plan_type": row[1],
                    "status": row[2],
                    "created_at": str(row[3]) if row[3] else None
                })

            is_real = {
                "has_onboarding": len(onboardings) > 0,
                "has_timeline": len(timeline) > 0,
                "has_checkins": len(checkins) > 0,
                "has_plans": len(plans) > 0,
                "valid_email": bool(client_data["email"] and "@" in client_data["email"]),
                "valid_phone": bool(client_data["phone"] and len(client_data["phone"]) >= 10)
            }

            activity_score = sum(is_real.values())
            classification = "REAL" if activity_score >= 4 else "TESTE" if activity_score <= 2 else "DUVIDOSO"

            return {
                "status": "ok",
                "client": client_data,
                "audit": {
                    "onboardings": onboardings,
                    "timeline_events": timeline,
                    "checkins": checkins,
                    "plans": plans
                },
                "validation": {
                    "criteria": is_real,
                    "activity_score": f"{activity_score}/6",
                    "classification": classification,
                    "recommendation": "MANTER" if classification == "REAL" else ("DELETAR" if classification == "TESTE" else "INVESTIGAR MANUALMENTE")
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))