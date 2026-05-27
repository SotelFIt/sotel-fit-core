import logging
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from twilio.rest import Client as TwilioClient
import os
from datetime import date, timedelta
from core.database import get_db
from core.security import verify_dual_auth
from services.audit_service import audit_log
from schemas.subscription import ActivateSubscriptionRequest, RenewSubscriptionRequest, SubscriptionResponse
from services.subscription_service import activate_subscription, renew_subscription, get_subscription, get_expiring_subscriptions, get_expired_subscriptions
from models.conversation_state import ConversationState

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
    return f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone

def get_twilio_from() -> str:
    return os.getenv("TWILIO_FROM_NUMBER") or os.getenv("TWILIO_WHATSAPP_FROM") or "whatsapp:+14155238886"

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

@router.post("/twilio/send-retention/{client_id}")
async def send_retention_message(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    from services.twilio_service import send_whatsapp_message
    client = db.execute(
        text("SELECT id, name, phone FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    _, name, phone = client
    if not phone:
        raise HTTPException(status_code=400, detail="Cliente sem telefone")
    first_name = (name or "").split()[0] if name else "cliente"
    message = (
        f"Oi {first_name}! Tudo bem?\n\n"
        f"Notei que faz um tempo que voce nao aparece no Sotel Fit Core.\n\n"
        f"Seu treino e dieta estao te esperando. Qualquer duvida, estou aqui.\n\n"
        f"Acesse: https://sotel-client.vercel.app"
    )
    success = send_whatsapp_message(phone, message)
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao enviar WhatsApp")
    return {"status": "success", "phone": phone, "message": message}