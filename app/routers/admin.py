import logging
from fastapi import APIRouter, HTTPException, Header, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from twilio.rest import Client as TwilioClient
import os
from core.database import get_db
from core.security import verify_dual_auth
from schemas.subscription import ActivateSubscriptionRequest, RenewSubscriptionRequest, SubscriptionResponse
from services.subscription_service import activate_subscription, renew_subscription, get_subscription, get_expiring_subscriptions, get_expired_subscriptions
from models.conversation_state import ConversationState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

ONBOARDING_LINK = "https://sotel-client.vercel.app/onboarding"
APP_LINK = "https://sotel-client.vercel.app"


def require_admin(auth_client_id: int = Depends(verify_dual_auth)):
    if auth_client_id != 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas admin pode acessar este endpoint")
    return auth_client_id


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


@router.post("/clients/{client_id}/activate-subscription", response_model=SubscriptionResponse)
def activate(client_id: int, payload: ActivateSubscriptionRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    return activate_subscription(db=db, client_id=client_id, plan_type=payload.plan_type, payment_method=payload.payment_method, notes=payload.notes)

@router.post("/clients/{client_id}/renew-subscription", response_model=SubscriptionResponse)
def renew(client_id: int, payload: RenewSubscriptionRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    return renew_subscription(db=db, client_id=client_id, plan_type=payload.plan_type, payment_method=payload.payment_method, notes=payload.notes)

@router.get("/clients/{client_id}/subscription", response_model=SubscriptionResponse)
def get_sub(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    sub = get_subscription(db, client_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Assinatura nao encontrada")
    return sub

@router.get("/subscriptions/expiring")
def list_expiring(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    return get_expiring_subscriptions(db)

@router.get("/subscriptions/expired")
def list_expired(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    return get_expired_subscriptions(db)

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
    twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
    twilio_client.messages.create(from_=os.getenv("TWILIO_WHATSAPP_FROM"), to=payload.phone, body=f"Seu acesso ao Sotel Fit Core foi liberado.\n\nAcesse aqui:\n{ONBOARDING_LINK}")
    return {"status": "success", "phone": payload.phone, "message": "Lead ativado"}

@router.post("/twilio/release-plan")
def release_plan(payload: ReleasePlanRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    state = db.query(ConversationState).filter(ConversationState.phone == payload.phone).first()
    if not state:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")
    state.status = "active"
    state.step = "active"
    db.commit()
    twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
    twilio_client.messages.create(from_=os.getenv("TWILIO_WHATSAPP_FROM"), to=payload.phone, body=f"Seu plano ja esta disponivel.\n\nAcesse aqui:\n{APP_LINK}")
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

@router.post("/clients/{client_id}/save-plan")
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

def save_client_plan(client_id: int, payload: SavePlanRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    try:
        db.execute(text("UPDATE client_plans SET status = 'inactive' WHERE client_id = :cid"), {"cid": client_id})
        db.execute(text("INSERT INTO client_plans (client_id, content, status, created_at) VALUES (:cid, :content, 'active', NOW())"), {"cid": client_id, "content": payload.content})
        db.commit()
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
        return {"status": "ok", "message": "Plano completo salvo"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/checkin")
def save_checkin(payload: CheckinRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    try:
        db.execute(text("INSERT INTO client_checkins (client_id, treinou, seguiu_dieta, peso, energia, dificuldade, observacoes, created_at) VALUES (:cid, :treinou, :seguiu_dieta, :peso, :energia, :dificuldade, :observacoes, NOW())"),
                   {"cid": payload.client_id, "treinou": payload.treinou, "seguiu_dieta": payload.seguiu_dieta, "peso": payload.peso, "energia": payload.energia, "dificuldade": payload.dificuldade, "observacoes": payload.observacoes})
        db.commit()
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
    """Envia lembretes de check-in para clientes ativos."""
    
    from services.checkin_reminder import send_checkin_reminders
    result = send_checkin_reminders()
    return result

@router.get("/clients")
def list_clients_admin(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    rows = db.execute(text("SELECT id, name, phone, objective, status FROM clients ORDER BY created_at DESC")).fetchall()
    return [{"id": r[0], "name": r[1], "phone": r[2], "objective": r[3], "status": r[4]} for r in rows]
