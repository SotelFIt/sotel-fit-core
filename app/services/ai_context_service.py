import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def get_client_context(db: Session, client_id: int) -> Optional[dict]:
    client_row = db.execute(
        text("SELECT id, name, phone, objective, status, age, weight, height FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()

    if not client_row:
        return None

    client = {
        "id": client_row[0],
        "name": client_row[1],
        "phone": client_row[2],
        "objective": client_row[3],
        "status": client_row[4],
        "age": client_row[5],
        "weight": client_row[6],
        "height": client_row[7],
    }

    sub_row = db.execute(
        text("""
            SELECT status, plan_type, payment_status, start_date, end_date, next_payment_date
            FROM subscriptions WHERE client_id = :cid LIMIT 1
        """),
        {"cid": client_id}
    ).fetchone()

    subscription = None
    if sub_row:
        end_date = sub_row[4]
        days_until_expiry = None
        if end_date:
            delta = end_date - datetime.utcnow().date()
            days_until_expiry = delta.days
        subscription = {
            "status": sub_row[0],
            "plan_type": sub_row[1],
            "payment_status": sub_row[2],
            "start_date": str(sub_row[3]) if sub_row[3] else None,
            "end_date": str(end_date) if end_date else None,
            "next_payment_date": str(sub_row[5]) if sub_row[5] else None,
            "days_until_expiry": days_until_expiry,
        }

    since = datetime.utcnow() - timedelta(days=28)
    checkin_rows = db.execute(
        text("""
            SELECT id, treinou, seguiu_dieta, peso, energia, dificuldade, observacoes, created_at
            FROM client_checkins
            WHERE client_id = :cid AND created_at >= :since
            ORDER BY created_at DESC
        """),
        {"cid": client_id, "since": since}
    ).fetchall()

    checkins = [
        {
            "id": r[0],
            "treinou": r[1],
            "seguiu_dieta": r[2],
            "peso": r[3],
            "energia": r[4],
            "dificuldade": r[5],
            "observacoes": r[6],
            "created_at": str(r[7]),
        }
        for r in checkin_rows
    ]

    plan_row = db.execute(
        text("""
            SELECT id, content, status, created_at
            FROM client_plans WHERE client_id = :cid AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        """),
        {"cid": client_id}
    ).fetchone()

    active_plan = None
    if plan_row:
        active_plan = {
            "id": plan_row[0],
            "has_content": bool(plan_row[1] and plan_row[1].strip()),
            "status": plan_row[2],
            "created_at": str(plan_row[3]),
        }

    diet_row = db.execute(
        text("""
            SELECT id, content, status, created_at
            FROM client_diets WHERE client_id = :cid AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        """),
        {"cid": client_id}
    ).fetchone()

    active_diet = None
    if diet_row:
        active_diet = {
            "id": diet_row[0],
            "has_content": bool(diet_row[1] and diet_row[1].strip()),
            "status": diet_row[2],
            "created_at": str(diet_row[3]),
        }

    return {
        "client": client,
        "subscription": subscription,
        "checkins_last_28d": checkins,
        "active_plan": active_plan,
        "active_diet": active_diet,
        "context_generated_at": datetime.utcnow().isoformat(),
    }


def get_all_active_clients_summary(db: Session) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT c.id, c.name, c.phone, c.objective, c.status,
                   s.status as sub_status, s.end_date, s.payment_status
            FROM clients c
            LEFT JOIN subscriptions s ON s.client_id = c.id
            WHERE c.status != 'inactive'
            ORDER BY c.created_at DESC
            LIMIT 500
        """)
    ).fetchall()

    clients = []
    for r in rows:
        end_date = r[6]
        days_until_expiry = None
        if end_date:
            delta = end_date - datetime.utcnow().date()
            days_until_expiry = delta.days

        clients.append({
            "id": r[0],
            "name": r[1],
            "phone": r[2],
            "objective": r[3],
            "status": r[4],
            "sub_status": r[5],
            "end_date": str(end_date) if end_date else None,
            "days_until_expiry": days_until_expiry,
            "payment_status": r[7],
        })

    return clients
