import logging
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from twilio.rest import Client as TwilioClient
import os
import json
from datetime import date, datetime, timedelta
from core.database import get_db
from core.security import verify_dual_auth
from services.audit_service import audit_log
from schemas.subscription import ActivateSubscriptionRequest, RenewSubscriptionRequest, SubscriptionResponse
from services.subscription_service import activate_subscription, renew_subscription, get_subscription, get_expiring_subscriptions, get_expired_subscriptions
from models.conversation_state import ConversationState
from services.workout_ai import gerar_treino_base
from services.diet_ai import gerar_dieta_base
from services.client_safe import make_client_safe, EMPTY_FALLBACK
from services.ai_coach_service import gerar_insights

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

ONBOARDING_LINK = "https://sotel-client.vercel.app/onboarding"
APP_LINK = "https://sotel-client.vercel.app"

ADMIN_CLIENT_IDS = {0, 2}

def require_admin(auth_client_id: int = Depends(verify_dual_auth)):
    if auth_client_id not in ADMIN_CLIENT_IDS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas admin pode acessar este endpoint")
    return auth_client_id

def whatsapp_to(phone: str) -> str:
    if phone.startswith("whatsapp:"):
        return phone
    p = phone.strip()
    if not p.startswith("+"):
        p = "+" + p
    return f"whatsapp:{p}"

def get_twilio_from() -> str:
    return os.getenv("TWILIO_FROM_NUMBER") or os.getenv("TWILIO_WHATSAPP_FROM") or "whatsapp:+14155238886"


def _send_template_tracked(db: Session, client_id: int, phone: str, name: str, content_sid: str, context: str):
    """Envia WhatsApp via template aprovado COM rastreio: status_callback + whatsapp_events + SID.

    Templates aprovados entregam fora da janela de 24h. Mantem todo o rastreamento do PR #4
    (SID, callback, whatsapp_events, audit_log, accepted, delivery, context).
    """
    to = whatsapp_to(phone)
    callback = os.getenv("PUBLIC_BACKEND_URL", "").strip().rstrip("/") + "/webhook/twilio-status"
    try:
        twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        msg = twilio_client.messages.create(
            from_=get_twilio_from(),
            to=to,
            content_sid=content_sid,
            content_variables=json.dumps({"1": name or "aluno", "2": APP_LINK}),
            status_callback=callback,
        )
        db.execute(
            text("""INSERT INTO whatsapp_events (client_id, message_sid, status, to_phone, context, created_at, updated_at)
                    VALUES (:cid, :sid, :st, :to, :ctx, NOW(), NOW())"""),
            {"cid": client_id, "sid": msg.sid, "st": msg.status, "to": to, "ctx": context}
        )
        db.commit()
        audit_log(db, action="whatsapp_sent", client_id=client_id, details=f"{context}: sid={msg.sid} status={msg.status}")
        return {
            "accepted": True,
            "sid": msg.sid,
            "status": msg.status,
            "delivery": "pending",
            "to": to,
            "context": context,
        }
    except Exception as e:
        code = getattr(e, "code", None)
        try:
            db.execute(
                text("""INSERT INTO whatsapp_events (client_id, message_sid, status, error_code, to_phone, context, created_at, updated_at)
                        VALUES (:cid, NULL, 'failed', :ec, :to, :ctx, NOW(), NOW())"""),
                {"cid": client_id, "ec": str(code) if code else "unknown", "to": to, "ctx": context}
            )
            db.commit()
        except Exception as inner:
            db.rollback()
            logger.error(f"Falha ao gravar whatsapp_event failed ({context}): {inner}")
        audit_log(db, action="whatsapp_failed", client_id=client_id, details=f"{context}: code={code}")
        raise HTTPException(status_code=502, detail={"accepted": False, "error_code": code, "error": str(e)})

class ActivateLeadRequest(BaseModel):
    phone: str

class ReleasePlanRequest(BaseModel):
    phone: str

class SavePlanRequest(BaseModel):
    content: str

class SaveDietRequest(BaseModel):
    content: str

class SaveFullPlanRequest(BaseModel):
    training_content: str = ""
    diet_content: str = ""
    release_to_client: bool = False

class CheckinRequest(BaseModel):
    client_id: int
    treinou: Optional[str] = None
    seguiu_dieta: Optional[str] = None
    peso: Optional[float] = None
    energia: Optional[str] = None
    dificuldade: Optional[str] = None
    observacoes: Optional[str] = None

class SubscriptionPayload(BaseModel):
    plan_type: str = "monthly"
    payment_method: str = "pix"
    notes: Optional[str] = None


PLAN_DAYS = {"monthly": 30, "quarterly": 90, "semiannual": 180, "annual": 365}


def _upsert_subscription(db, client_id, plan_type, payment_method, notes, renew=False):
    days = PLAN_DAYS.get(plan_type, 30)
    today = date.today()
    end_date = today + timedelta(days=days)

    existing = db.execute(
        text("SELECT id, end_date FROM subscriptions WHERE client_id = :cid LIMIT 1"),
        {"cid": client_id}
    ).fetchone()

    if existing:
        if renew and existing[1] and existing[1] >= today:
            end_date = existing[1] + timedelta(days=days)
        db.execute(text("""
            UPDATE subscriptions SET
                status = 'active', plan_type = :plan_type, payment_status = 'paid',
                manual_payment_method = :method, start_date = :start, end_date = :end,
                last_payment_date = :start, next_payment_date = :end,
                notes = :notes, updated_at = NOW()
            WHERE client_id = :cid
        """), {"plan_type": plan_type, "method": payment_method,
               "start": today, "end": end_date, "notes": notes, "cid": client_id})
    else:
        db.execute(text("""
            INSERT INTO subscriptions (client_id, status, plan_type, payment_status,
                manual_payment_method, start_date, end_date, last_payment_date,
                next_payment_date, notes, created_at, updated_at)
            VALUES (:cid, 'active', :plan_type, 'paid', :method, :start, :end,
                :start, :end, :notes, NOW(), NOW())
        """), {"cid": client_id, "plan_type": plan_type, "method": payment_method,
               "start": today, "end": end_date, "notes": notes})

    db.commit()

    sub = db.execute(
        text("""SELECT id, client_id, status, plan_type, payment_status, start_date,
                end_date, last_payment_date, next_payment_date, manual_payment_method,
                notes, created_at, updated_at
                FROM subscriptions WHERE client_id = :cid LIMIT 1"""),
        {"cid": client_id}
    ).fetchone()

    return {
        "id": sub[0], "client_id": sub[1], "status": sub[2], "plan_type": sub[3],
        "payment_status": sub[4], "start_date": str(sub[5]) if sub[5] else None,
        "end_date": str(sub[6]) if sub[6] else None,
        "last_payment_date": str(sub[7]) if sub[7] else None,
        "next_payment_date": str(sub[8]) if sub[8] else None,
        "manual_payment_method": sub[9], "notes": sub[10],
        "created_at": str(sub[11]), "updated_at": str(sub[12])
    }


@router.post("/clients/{client_id}/activate-subscription")
def activate(client_id: int, payload: SubscriptionPayload, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    try:
        return _upsert_subscription(db, client_id, payload.plan_type, payload.payment_method, payload.notes, renew=False)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clients/{client_id}/renew-subscription")
def renew(client_id: int, payload: SubscriptionPayload, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    try:
        return _upsert_subscription(db, client_id, payload.plan_type, payload.payment_method, payload.notes, renew=True)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/clients/{client_id}/subscription")
def get_sub(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    sub = db.execute(
        text("""SELECT id, client_id, status, plan_type, payment_status, start_date,
                end_date, last_payment_date, next_payment_date, manual_payment_method,
                notes, created_at, updated_at
                FROM subscriptions WHERE client_id = :cid LIMIT 1"""),
        {"cid": client_id}
    ).fetchone()
    if not sub:
        raise HTTPException(status_code=404, detail="Assinatura nao encontrada")
    return {
        "id": sub[0], "client_id": sub[1], "status": sub[2], "plan_type": sub[3],
        "payment_status": sub[4], "start_date": str(sub[5]) if sub[5] else None,
        "end_date": str(sub[6]) if sub[6] else None,
        "last_payment_date": str(sub[7]) if sub[7] else None,
        "next_payment_date": str(sub[8]) if sub[8] else None,
        "manual_payment_method": sub[9], "notes": sub[10],
        "created_at": str(sub[11]), "updated_at": str(sub[12])
    }

@router.get("/subscriptions/expiring")
def list_expiring(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    today = date.today()
    threshold = today + timedelta(days=7)
    rows = db.execute(text("""
        SELECT s.client_id, c.name, c.email, c.phone, s.status, s.plan_type, s.end_date
        FROM subscriptions s JOIN clients c ON s.client_id = c.id
        WHERE s.end_date >= :today AND s.end_date <= :threshold AND s.status IN ('active', 'expiring')
    """), {"today": today, "threshold": threshold}).fetchall()
    return [{"client_id": r[0], "client_name": r[1], "client_email": r[2], "client_phone": r[3],
             "status": r[4], "plan_type": r[5], "end_date": str(r[6])} for r in rows]

@router.get("/subscriptions/expired")
def list_expired(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    rows = db.execute(text("""
        SELECT s.client_id, c.name, c.email, c.phone, s.status, s.plan_type, s.end_date
        FROM subscriptions s JOIN clients c ON s.client_id = c.id
        WHERE s.status = 'expired'
    """)).fetchall()
    return [{"client_id": r[0], "client_name": r[1], "client_email": r[2], "client_phone": r[3],
             "status": r[4], "plan_type": r[5], "end_date": str(r[6])} for r in rows]

@router.post("/twilio/activate-lead")
def activate_lead(payload: ActivateLeadRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    state = db.query(ConversationState).filter(ConversationState.phone == payload.phone).first()
    if not state:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")
    state.status = "onboarding_pending"
    state.step = "active_client"
    if state.onboarding_link_sent:
        return {"status": "skipped", "phone": payload.phone, "message": "Link ja enviado anteriormente"}
    state.onboarding_link_sent = True
    db.commit()
    try:
        twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        twilio_client.messages.create(
            from_=get_twilio_from(),
            to=whatsapp_to(payload.phone),
            content_sid=os.getenv("TWILIO_TEMPLATE_PLANO"),
            messaging_service_sid=None
        )
        logger.info(f"WhatsApp enviado para {payload.phone}")
    except Exception as e:
        logger.error(f"Erro ao enviar WhatsApp activate-lead: {e}")
    audit_log(db, action="activate_lead", client_id=None, details=f"phone={payload.phone}")
    return {"status": "success", "phone": payload.phone, "message": "Lead ativado"}

@router.post("/twilio/release-plan")
def release_plan(payload: ReleasePlanRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    state = db.query(ConversationState).filter(ConversationState.phone == payload.phone).first()
    if not state:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")
    state.status = "active"
    state.step = "active"
    db.execute(
        text("UPDATE clients SET status = 'active' WHERE phone = :p"),
        {"p": payload.phone}
    )
    db.commit()
    try:
        twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        twilio_client.messages.create(
            from_=get_twilio_from(),
            to=whatsapp_to(payload.phone),
            body=f"Seu plano ja esta disponivel.\n\nAcesse aqui:\n{APP_LINK}"
        )
        logger.info(f"WhatsApp release-plan enviado para {payload.phone}")
    except Exception as e:
        logger.error(f"Erro ao enviar WhatsApp release-plan: {e}")
    audit_log(db, action="release_plan", client_id=None, details=f"phone={payload.phone}")
    return {"status": "success", "phone": payload.phone, "message": "Plano liberado"}

@router.get("/leads")
def list_leads(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    leads = db.query(ConversationState).all()
    return [{"phone": l.phone, "name": l.name, "goal": l.goal, "routine": l.routine, "status": l.status, "step": l.step, "onboarding_link_sent": l.onboarding_link_sent, "created_at": l.created_at} for l in leads]

@router.get("/onboardings")
def list_onboardings(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    from models.lead_onboarding import LeadOnboarding
    onboardings = db.query(LeadOnboarding).order_by(LeadOnboarding.created_at.desc()).all()
    return [{"id": o.id, "phone": o.phone, "nome": o.nome, "email": o.email, "telefone": o.telefone, "idade": o.idade, "peso": o.peso, "altura": o.altura, "objetivo": o.objetivo, "nivel_treino": o.nivel_treino, "dias_treino": o.dias_treino, "horario_treino": o.horario_treino, "lesoes": o.lesoes, "alimentacao_atual": o.alimentacao_atual, "maior_dificuldade": o.maior_dificuldade, "meta_principal": o.meta_principal, "observacoes": o.observacoes, "created_at": o.created_at} for o in onboardings]

@router.get("/onboardings/by-phone/{phone}")
def get_onboarding_by_phone(phone: str, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    from models.lead_onboarding import LeadOnboarding
    o = db.query(LeadOnboarding).filter(LeadOnboarding.phone == phone).order_by(LeadOnboarding.created_at.desc()).first()
    if not o:
        return None
    return {"id": o.id, "phone": o.phone, "nome": o.nome, "email": o.email, "telefone": o.telefone, "idade": o.idade, "peso": o.peso, "altura": o.altura, "objetivo": o.objetivo, "nivel_treino": o.nivel_treino, "dias_treino": o.dias_treino, "horario_treino": o.horario_treino, "lesoes": o.lesoes, "alimentacao_atual": o.alimentacao_atual, "maior_dificuldade": o.maior_dificuldade, "meta_principal": o.meta_principal, "observacoes": o.observacoes, "created_at": o.created_at}

@router.get("/clients/{client_id}/plan")
def get_client_plan(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    result = db.execute(
        text("SELECT id, client_id, content, status, created_at FROM client_plans WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
        {"cid": client_id}
    ).fetchone()
    if not result:
        return {"content": ""}
    return {"id": result[0], "client_id": result[1], "content": result[2], "status": result[3], "created_at": str(result[4])}

@router.get("/clients/{client_id}/diet")
def get_client_diet(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    result = db.execute(
        text("SELECT id, client_id, content, status, created_at FROM client_diets WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
        {"cid": client_id}
    ).fetchone()
    if not result:
        return {"content": ""}
    return {"id": result[0], "client_id": result[1], "content": result[2], "status": result[3], "created_at": str(result[4])}

@router.post("/clients/{client_id}/save-plan")
def save_client_plan(client_id: int, payload: SavePlanRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    try:
        db.execute(text("UPDATE client_plans SET status = 'inactive' WHERE client_id = :cid"), {"cid": client_id})
        db.execute(text("INSERT INTO client_plans (client_id, content, status, created_at) VALUES (:cid, :content, 'active', NOW())"), {"cid": client_id, "content": payload.content})
        db.commit()
        audit_log(db, action="save_plan", client_id=client_id, details="treino atualizado")
        return {"status": "ok", "message": "Plano salvo com sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clients/{client_id}/save-diet")
def save_client_diet(client_id: int, payload: SaveDietRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    try:
        db.execute(text("UPDATE client_diets SET status = 'inactive' WHERE client_id = :cid"), {"cid": client_id})
        db.execute(text("INSERT INTO client_diets (client_id, content, status, created_at) VALUES (:cid, :content, 'active', NOW())"), {"cid": client_id, "content": payload.content})
        db.commit()
        audit_log(db, action="save_diet", client_id=client_id, details="dieta atualizada")
        return {"status": "ok", "message": "Dieta salva com sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clients/{client_id}/save-full-plan")
def save_full_plan(client_id: int, payload: SaveFullPlanRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    try:
        if payload.training_content:
            db.execute(text("UPDATE client_plans SET status = 'inactive' WHERE client_id = :cid"), {"cid": client_id})
            db.execute(text("INSERT INTO client_plans (client_id, content, status, created_at) VALUES (:cid, :content, 'active', NOW())"), {"cid": client_id, "content": payload.training_content})
        if payload.diet_content:
            db.execute(text("UPDATE client_diets SET status = 'inactive' WHERE client_id = :cid"), {"cid": client_id})
            db.execute(text("INSERT INTO client_diets (client_id, content, status, created_at) VALUES (:cid, :content, 'active', NOW())"), {"cid": client_id, "content": payload.diet_content})
        db.commit()
        audit_log(db, action="save_full_plan", client_id=client_id, details=f"release={payload.release_to_client}")
        return {"status": "ok", "message": "Plano completo salvo"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clients/{client_id}/release-plan")
def release_plan_by_id(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    client = db.execute(
        text("SELECT id, phone, status, name FROM clients WHERE id = :cid LIMIT 1"),
        {"cid": client_id}
    ).fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")

    phone = client[1]
    client_name = client[3] or "Cliente"

    plan = db.execute(
        text("SELECT id, content FROM client_plans WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
        {"cid": client_id}
    ).fetchone()
    if not plan or not (plan[1] or "").strip():
        return {"success": False, "error": "Cliente nao possui treino cadastrado ou treino esta vazio"}

    diet = db.execute(
        text("SELECT id, content FROM client_diets WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
        {"cid": client_id}
    ).fetchone()
    if not diet or not (diet[1] or "").strip():
        return {"success": False, "error": "Cliente nao possui dieta cadastrada ou dieta esta vazia"}

    if not phone or len(phone.strip()) < 8:
        return {"success": False, "error": "Cliente nao possui telefone valido"}

    try:
        plan_safe = make_client_safe(plan[1])
        diet_safe = make_client_safe(diet[1])
    except Exception as e:
        logger.error(f"Falha ao sanitizar conteudo client_id={client_id}: {e}")
        raise HTTPException(status_code=500, detail="Falha ao sanitizar conteudo. Plano NAO foi liberado.")

    if plan_safe == EMPTY_FALLBACK or diet_safe == EMPTY_FALLBACK:
        return {"success": False, "error": "Treino ou dieta nao possuem conteudo valido para publicacao."}

    try:
        db.execute(text("UPDATE client_plans SET published_content = :pc WHERE id = :pid"),
                   {"pc": plan_safe, "pid": plan[0]})
        db.execute(text("UPDATE client_diets SET published_content = :dc WHERE id = :did"),
                   {"dc": diet_safe, "did": diet[0]})
        db.execute(text("UPDATE clients SET status = 'active' WHERE id = :cid"), {"cid": client_id})
        db.execute(
            text("UPDATE conversation_states SET status = 'active', step = 'active' WHERE phone = :p"),
            {"p": phone}
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Falha ao publicar plano client_id={client_id}: {e}")
        raise HTTPException(status_code=500, detail="Falha ao publicar plano. Tente novamente.")

    whatsapp_sent = False
    whatsapp_error = None
    try:
        twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        msg = twilio_client.messages.create(
            from_=get_twilio_from(),
            to=whatsapp_to(phone),
            content_sid=os.getenv("TWILIO_TEMPLATE_PLANO"),
            content_variables=json.dumps({"1": client_name, "2": APP_LINK}),
            status_callback=os.getenv("PUBLIC_BACKEND_URL", "").strip().rstrip("/") + "/webhook/twilio-status"
        )
        whatsapp_sent = True
        db.execute(
            text("""INSERT INTO whatsapp_events (client_id, message_sid, status, to_phone, context, created_at, updated_at)
                    VALUES (:cid, :sid, :st, :to, 'release_plan', NOW(), NOW())"""),
            {"cid": client_id, "sid": msg.sid, "st": msg.status, "to": whatsapp_to(phone)}
        )
        db.commit()
        logger.info(f"WhatsApp release-plan enviado client_id={client_id} sid={msg.sid} status={msg.status}")
    except Exception as e:
        _code = getattr(e, "code", None)
        _msg = getattr(e, "msg", None)
        _details = getattr(e, "details", None)
        whatsapp_error = f"code={_code} msg={_msg} details={_details} raw={str(e)}"
        logger.error(f"Erro WhatsApp release-plan client_id={client_id}: {whatsapp_error}")
        try:
            db.execute(
                text("""INSERT INTO whatsapp_events (client_id, message_sid, status, error_code, to_phone, context, created_at, updated_at)
                        VALUES (:cid, NULL, 'failed', :ec, :to, 'release_plan', NOW(), NOW())"""),
                {"cid": client_id, "ec": str(_code) if _code else "unknown", "to": whatsapp_to(phone)}
            )
            db.commit()
        except Exception as inner:
            db.rollback()
            logger.error(f"Falha ao gravar whatsapp_event failed: {inner}")

    if whatsapp_sent:
        audit_log(db, action="whatsapp_sent", client_id=client_id, details="release-plan: plano liberado")
    else:
        audit_log(db, action="whatsapp_failed", client_id=client_id, details=f"release-plan: {whatsapp_error}")

    return {
        "success": True,
        "client_id": client_id,
        "status": "active",
        "whatsapp_sent": whatsapp_sent,
        "whatsapp_error": whatsapp_error
    }


@router.get("/whatsapp-events/{client_id}")
def whatsapp_events_by_client(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    rows = db.execute(
        text("SELECT id, client_id, message_sid, status, error_code, to_phone, context, created_at, updated_at FROM whatsapp_events WHERE client_id = :cid ORDER BY created_at DESC LIMIT 50"),
        {"cid": client_id}
    ).fetchall()
    return [
        {
            "id": r[0], "client_id": r[1], "message_sid": r[2], "status": r[3],
            "error_code": r[4], "to_phone": r[5], "context": r[6],
            "created_at": str(r[7]), "updated_at": str(r[8])
        }
        for r in rows
    ]


@router.get("/operations-center")
def operations_center(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    clients = db.execute(
        text("""SELECT id, name, phone, status FROM clients
        WHERE status != \'inactive\'
          AND (objective IS NULL OR objective != \'admin\')
        ORDER BY id""")
    ).fetchall()

    plan_rows = db.execute(
        text("SELECT DISTINCT client_id FROM client_plans WHERE status = \'active\'")
    ).fetchall()
    plan_ids = {r[0] for r in plan_rows}

    diet_rows = db.execute(
        text("SELECT DISTINCT client_id FROM client_diets WHERE status = \'active\'")
    ).fetchall()
    diet_ids = {r[0] for r in diet_rows}

    wa_rows = db.execute(
        text("""
            SELECT DISTINCT ON (client_id) client_id, action
            FROM admin_audit_log
            WHERE action IN (\'whatsapp_sent\', \'whatsapp_failed\') AND client_id IS NOT NULL
            ORDER BY client_id, created_at DESC
        """)
    ).fetchall()
    wa_map = {r[0]: r[1] for r in wa_rows}

    STATUS_TO_CARD = {"onboarding_pending": "onboarding", "waiting_plan": "waiting_plan", "active": "active"}

    summary = {"onboarding": 0, "waiting_plan": 0, "active": 0, "problems": 0}
    lead = 0
    result = []

    for c in clients:
        cid, name, phone, status = c[0], c[1], c[2], c[3]
        has_training = cid in plan_ids
        has_diet = cid in diet_ids

        wa_action = wa_map.get(cid)
        if wa_action == "whatsapp_sent":
            whatsapp_state = "sent"
        elif wa_action == "whatsapp_failed":
            whatsapp_state = "failed"
        else:
            whatsapp_state = "never"

        problem = None
        action = "OK"

        if status == "waiting_plan":
            if not has_training:
                problem, action = "Treino nao criado", "Criar treino"
            elif not has_diet:
                problem, action = "Dieta nao criada", "Criar dieta"
            else:
                problem, action = "Plano pronto, cliente nao liberado", "Liberar cliente"
        elif status == "active":
            if not has_training:
                problem, action = "Cliente ativo sem treino", "Corrigir treino"
            elif not has_diet:
                problem, action = "Cliente ativo sem dieta", "Corrigir dieta"
            elif whatsapp_state == "failed":
                problem, action = "WhatsApp falhou", "Reenviar WhatsApp"

        card = STATUS_TO_CARD.get(status)
        if card:
            summary[card] += 1
        elif status == "lead":
            lead += 1
        if problem:
            summary["problems"] += 1

        result.append({
            "client_id": cid,
            "name": name,
            "phone": phone,
            "status": status,
            "has_onboarding": True,
            "has_training": has_training,
            "has_diet": has_diet,
            "whatsapp_state": whatsapp_state,
            "problem": problem,
            "action": action,
        })

    expiring_7d = len(get_expiring_subscriptions(db))
    expired = len(get_expired_subscriptions(db))
    summary["pipeline"] = {
        "lead": lead,
        "onboarding": summary["onboarding"],
        "waiting_plan": summary["waiting_plan"],
        "active": summary["active"],
        "expiring_7d": expiring_7d,
        "expired": expired,
        "problems": summary["problems"],
        "pipeline_open": lead + summary["onboarding"] + summary["waiting_plan"],
        "as_of": datetime.utcnow().isoformat(),
    }
    return {"summary": summary, "clients": result}


@router.post("/checkin")
def save_checkin(payload: CheckinRequest, db: Session = Depends(get_db)):
    try:
        db.execute(
            text("INSERT INTO client_checkins (client_id, treinou, seguiu_dieta, peso, energia, dificuldade, observacoes, created_at) VALUES (:cid, :treinou, :seguiu_dieta, :peso, :energia, :dificuldade, :observacoes, NOW())"),
            {"cid": payload.client_id, "treinou": payload.treinou, "seguiu_dieta": payload.seguiu_dieta, "peso": payload.peso, "energia": payload.energia, "dificuldade": payload.dificuldade, "observacoes": payload.observacoes}
        )
        db.commit()

        try:
            from routers.timeline import create_event
            energia = int(payload.energia or 0)
            treinou = int(payload.treinou or 0)
            if energia >= 4 and treinou >= 4:
                title, icon = "Check-in excelente!", "🔥"
            elif treinou >= 3:
                title, icon = "Check-in semanal concluido", "✅"
            else:
                title, icon = "Check-in registrado", "📋"
            desc = f"Treino: {payload.treinou}/5 · Dieta: {payload.seguiu_dieta}/5 · Energia: {payload.energia}/5"
            if payload.peso:
                desc += f" · Peso: {payload.peso}kg"
            create_event(db, payload.client_id, "checkin", title, desc, icon)

            total = db.execute(text("SELECT COUNT(*) FROM client_checkins WHERE client_id = :cid"), {"cid": payload.client_id}).scalar() or 0
            insight_title = None
            insight_desc = None
            insight_icon = "⚡"

            def safe_int(v):
                try:
                    return int(str(v).split('/')[0].strip())
                except Exception:
                    return 0

            avg = ((safe_int(payload.treinou) + safe_int(payload.seguiu_dieta) + safe_int(payload.energia)) / 3)

            if total == 1:
                insight_title = "Primeira semana registrada"
                insight_desc = "O sistema ja esta acompanhando sua evolucao. Continue assim."
                insight_icon = "🚀"
            elif total % 4 == 0:
                insight_title = "Um mes de consistencia"
                insight_desc = f"{total} check-ins concluidos. Consistencia e o maior diferencial."
                insight_icon = "📈"
            elif avg >= 4.5:
                insight_title = "Semana acima da media"
                insight_desc = "Treino, dieta e energia no nivel maximo. Ritmo de evolucao acelerado."
                insight_icon = "🔥"
            elif avg <= 2:
                insight_title = "Semana desafiadora detectada"
                insight_desc = "Queda na aderencia identificada. Seu personal sera notificado para ajuste."
                insight_icon = "💤"
            elif total >= 3:
                insight_title = "Padrao de consistencia identificado"
                insight_desc = "O sistema detectou presenca continua. Evolucao sustentavel em andamento."
                insight_icon = "🧠"

            if insight_title:
                already = db.execute(
                    text("SELECT COUNT(*) FROM timeline_events WHERE client_id = :cid AND event_type = 'ai_insight' AND title = :title AND created_at > NOW() - INTERVAL '7 days'"),
                    {"cid": payload.client_id, "title": insight_title}
                ).scalar() or 0
                if already == 0:
                    create_event(db, payload.client_id, "ai_insight", insight_title, insight_desc, insight_icon)

            try:
                if total in [4, 8, 12, 24]:
                    months = total // 4
                    label = "mes" if months == 1 else "meses"
                    ach_title = f"{months} {label} de consistencia"
                    already_ach = db.execute(
                        text("SELECT COUNT(*) FROM timeline_events WHERE client_id = :cid AND event_type = 'achievement' AND title = :title"),
                        {"cid": payload.client_id, "title": ach_title}
                    ).scalar() or 0
                    if already_ach == 0:
                        create_event(db, payload.client_id, "achievement", ach_title, f"{total} check-ins completados. Disciplina real em construcao.", "📈")

                recent = db.execute(text("SELECT treinou, seguiu_dieta, energia FROM client_checkins WHERE client_id = :cid ORDER BY created_at DESC LIMIT 3"), {"cid": payload.client_id}).fetchall()
                if len(recent) >= 3:
                    avgs = [sum([int(v or 0) for v in [r[0], r[1], r[2]]]) / 3 for r in recent]
                    if all(a >= 4 for a in avgs):
                        create_event(db, payload.client_id, "achievement", "Alta constancia detectada", "3 semanas consecutivas acima da media. IA registrou evolucao sustentavel.", "🧠")

                if total > 1:
                    all_rows = db.execute(text("SELECT treinou, seguiu_dieta, energia FROM client_checkins WHERE client_id = :cid ORDER BY created_at DESC"), {"cid": payload.client_id}).fetchall()
                    current_avg = avg
                    prev_avgs = [sum([int(v or 0) for v in [r[0], r[1], r[2]]]) / 3 for r in all_rows[1:]]
                    if prev_avgs and current_avg > max(prev_avgs) and current_avg >= 4:
                        create_event(db, payload.client_id, "achievement", "Melhor semana registrada", "Desempenho acima de todas as semanas anteriores. Novo recorde pessoal.", "🏆")
            except Exception:
                pass
        except Exception:
            pass

        return {"status": "ok", "message": "Check-in salvo com sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/checkins/{client_id}")
def get_checkins(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    rows = db.execute(
        text("SELECT id, client_id, treinou, seguiu_dieta, peso, energia, dificuldade, observacoes, created_at FROM client_checkins WHERE client_id = :cid ORDER BY created_at DESC"),
        {"cid": client_id}
    ).fetchall()
    return [{"id": r[0], "client_id": r[1], "treinou": r[2], "seguiu_dieta": r[3], "peso": r[4], "energia": r[5], "dificuldade": r[6], "observacoes": r[7], "created_at": str(r[8])} for r in rows]

@router.post("/send-checkin-reminders")
async def send_checkin_reminders_endpoint(_: int = Depends(require_admin)):
    from services.checkin_reminder import send_checkin_reminders
    result = send_checkin_reminders()
    return result

@router.get("/clients")
def list_clients_admin(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    rows = db.execute(text("SELECT id, name, phone, objective, status FROM clients WHERE status != 'inactive' ORDER BY created_at DESC LIMIT 500")).fetchall()
    return [{"id": r[0], "name": r[1], "phone": r[2], "objective": r[3], "status": r[4]} for r in rows]

@router.get("/clients/{client_id}/onboarding")
def get_client_onboarding(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    from models.lead_onboarding import LeadOnboarding
    client = db.execute(
        text("SELECT phone FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    phone = client[0] or ""
    phone_clean = phone.replace("whatsapp:", "")
    o = db.query(LeadOnboarding).filter(
        (LeadOnboarding.phone == phone) |
        (LeadOnboarding.phone == phone_clean) |
        (LeadOnboarding.phone == f"whatsapp:{phone_clean}")
    ).order_by(LeadOnboarding.created_at.desc()).first()
    if not o:
        return None
    return {
        "id": o.id, "phone": o.phone, "nome": o.nome, "email": o.email,
        "telefone": o.telefone, "idade": o.idade, "peso": o.peso, "altura": o.altura,
        "objetivo": o.objetivo, "nivel_treino": o.nivel_treino, "dias_treino": o.dias_treino,
        "horario_treino": o.horario_treino, "lesoes": o.lesoes,
        "alimentacao_atual": o.alimentacao_atual, "maior_dificuldade": o.maior_dificuldade,
        "meta_principal": o.meta_principal, "observacoes": o.observacoes,
        "created_at": o.created_at,
    }


@router.post("/twilio/resend-onboarding")
def resend_onboarding(payload: ActivateLeadRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    state = db.query(ConversationState).filter(ConversationState.phone == payload.phone).first()
    if not state:
        state = ConversationState(phone=payload.phone, step="active_client", status="onboarding_pending", onboarding_link_sent=False)
        db.add(state)
        db.commit()
        db.refresh(state)
    # Reset do flag para permitir reenvio
    state.onboarding_link_sent = False
    state.step = "active_client"
    state.status = "onboarding_pending"
    db.commit()
    try:
        twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        twilio_client.messages.create(
            from_=get_twilio_from(),
            to=whatsapp_to(payload.phone),
            content_sid=os.getenv("TWILIO_TEMPLATE_ONBOARDING"),
            messaging_service_sid=None
        )
        state.onboarding_link_sent = True
        db.commit()
        logger.info(f"Reenvio onboarding para {payload.phone}")
    except Exception as e:
        logger.error(f"Erro ao reenviar onboarding: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao enviar WhatsApp: {str(e)}")
    audit_log(db, action="resend_onboarding", client_id=None, details=f"phone={payload.phone}")
    return {"status": "success", "phone": payload.phone, "message": "Onboarding reenviado"}


@router.post("/twilio/resend-access/{client_id}")
def resend_access(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    client = db.execute(
        text("SELECT id, name, phone FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    _, name, phone = client
    if not phone:
        raise HTTPException(status_code=400, detail="Cliente sem telefone")
    return _send_template_tracked(db, client_id, phone, name, os.getenv("TWILIO_TEMPLATE_ACCESS"), "resend_access")

@router.post("/twilio/send-retention/{client_id}")
async def send_retention_message(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    client = db.execute(
        text("SELECT id, name, phone FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    _, name, phone = client
    if not phone:
        raise HTTPException(status_code=400, detail="Cliente sem telefone")
    return _send_template_tracked(db, client_id, phone, name, os.getenv("TWILIO_TEMPLATE_RETENTION"), "retention")

@router.post("/twilio/send-renewal/{client_id}")
async def send_renewal_message(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    client = db.execute(
        text("SELECT id, name, phone FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    _, name, phone = client
    if not phone:
        raise HTTPException(status_code=400, detail="Cliente sem telefone")
    return _send_template_tracked(db, client_id, phone, name, os.getenv("TWILIO_TEMPLATE_RENEWAL"), "renewal")


@router.post("/clients/{client_id}/generate-workout-draft")
def generate_workout_draft_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    draft = gerar_treino_base(db, client_id)
    return {"workout_draft": draft}


@router.post("/clients/{client_id}/generate-diet-draft")
def generate_diet_draft_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    draft = gerar_dieta_base(db, client_id)
    return {"diet_draft": draft}


@router.get("/clients/{client_id}/ai-insights")
def ai_insights_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return gerar_insights(db, client_id)
