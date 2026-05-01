from datetime import date, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from models.subscription import Subscription
from models.client import Client

PLAN_DAYS = {"monthly": 30, "quarterly": 90, "semiannual": 180, "annual": 365}
EXPIRING_DAYS_THRESHOLD = 7
ACCESS_BLOCKED_MESSAGE = "Seu plano está vencido. Renove para continuar acessando seu treino, plano alimentar e acompanhamento."

def _get_or_create_subscription(db, client_id):
    sub = db.query(Subscription).filter(Subscription.client_id == client_id).first()
    if not sub:
        sub = Subscription(client_id=client_id, status="lead", payment_status="pending")
        db.add(sub)
        db.flush()
    return sub

def _compute_status(end_date):
    if end_date is None:
        return "lead"
    today = date.today()
    if today > end_date:
        return "expired"
    if (end_date - today).days <= EXPIRING_DAYS_THRESHOLD:
        return "expiring"
    return "active"

def _days_remaining(end_date):
    if end_date is None:
        return None
    return max((end_date - date.today()).days, 0)

def _validate_plan_type(plan_type):
    if plan_type not in PLAN_DAYS:
        raise HTTPException(status_code=400, detail=f"plan_type invalido. Use: {', '.join(PLAN_DAYS)}")

def _validate_payment_method(payment_method):
    valid = ["pix", "card", "cash", "external_link", "other"]
    if payment_method not in valid:
        raise HTTPException(status_code=400, detail=f"payment_method invalido. Use: {', '.join(valid)}")

def _validate_client(db, client_id):
    if not db.query(Client).filter(Client.id == client_id).first():
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")

def activate_subscription(db, client_id, plan_type, payment_method, notes=None):
    _validate_client(db, client_id)
    _validate_plan_type(plan_type)
    _validate_payment_method(payment_method)
    sub = _get_or_create_subscription(db, client_id)
    today = date.today()
    days = PLAN_DAYS[plan_type]
    sub.status = "active"
    sub.plan_type = plan_type
    sub.payment_status = "paid"
    sub.start_date = today
    sub.end_date = today + timedelta(days=days)
    sub.last_payment_date = today
    sub.next_payment_date = sub.end_date
    sub.manual_payment_method = payment_method
    if notes:
        sub.notes = notes
    db.commit()
    db.refresh(sub)
    return sub

def renew_subscription(db, client_id, plan_type, payment_method, notes=None):
    _validate_client(db, client_id)
    _validate_plan_type(plan_type)
    _validate_payment_method(payment_method)
    sub = _get_or_create_subscription(db, client_id)
    today = date.today()
    days = PLAN_DAYS[plan_type]
    base_date = sub.end_date if (sub.end_date and sub.end_date >= today) else today
    sub.status = "active"
    sub.plan_type = plan_type
    sub.payment_status = "paid"
    sub.start_date = today
    sub.end_date = base_date + timedelta(days=days)
    sub.last_payment_date = today
    sub.next_payment_date = sub.end_date
    sub.manual_payment_method = payment_method
    if notes:
        sub.notes = notes
    db.commit()
    db.refresh(sub)
    return sub

def can_access_client_content(db, client_id):
    sub = db.query(Subscription).filter(Subscription.client_id == client_id).first()
    if not sub:
        return False
    new_status = _compute_status(sub.end_date)
    if new_status != sub.status and sub.status != "cancelled":
        sub.status = new_status
        db.commit()
    return sub.status in ["active", "expiring"]

def get_subscription(db, client_id):
    return db.query(Subscription).filter(Subscription.client_id == client_id).first()

def update_all_subscriptions_status(db):
    subs = db.query(Subscription).filter(Subscription.status.notin_(["cancelled", "lead"])).all()
    updated = 0
    for sub in subs:
        new_status = _compute_status(sub.end_date)
        if new_status != sub.status:
            sub.status = new_status
            updated += 1
    db.commit()
    return {"total_checked": len(subs), "total_updated": updated}

def get_expiring_subscriptions(db):
    today = date.today()
    threshold = today + timedelta(days=EXPIRING_DAYS_THRESHOLD)
    subs = db.query(Subscription, Client).join(Client, Subscription.client_id == Client.id).filter(
        Subscription.end_date >= today, Subscription.end_date <= threshold,
        Subscription.status.in_(["active", "expiring"])
    ).all()
    return [{"client_id": s.client_id, "client_name": c.name, "client_email": c.email,
             "client_phone": c.phone, "status": s.status, "plan_type": s.plan_type,
             "end_date": s.end_date, "days_remaining": _days_remaining(s.end_date)} for s, c in subs]

def get_expired_subscriptions(db):
    subs = db.query(Subscription, Client).join(Client, Subscription.client_id == Client.id).filter(
        Subscription.status == "expired").all()
    return [{"client_id": s.client_id, "client_name": c.name, "client_email": c.email,
             "client_phone": c.phone, "status": s.status, "plan_type": s.plan_type,
             "end_date": s.end_date, "days_remaining": 0} for s, c in subs]
