from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from twilio.rest import Client as TwilioClient
import os
from core.database import get_db
from core.security import verify_dual_auth
from schemas.subscription import ActivateSubscriptionRequest, RenewSubscriptionRequest, SubscriptionResponse
from services.subscription_service import activate_subscription, renew_subscription, get_subscription, get_expiring_subscriptions, get_expired_subscriptions
from models.conversation_state import ConversationState

router = APIRouter(prefix="/admin", tags=["admin"])

ONBOARDING_LINK = "https://frontend-iota-rose-78.vercel.app/onboarding"
APP_LINK = "https://frontend-iota-rose-78.vercel.app"


def require_admin(auth_client_id: int = Depends(verify_dual_auth)):
    if auth_client_id != 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas admin pode acessar este endpoint")
    return auth_client_id


class ActivateLeadRequest(BaseModel):
    phone: str


class ReleasePlanRequest(BaseModel):
    phone: str


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
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM")
    twilio_client = TwilioClient(account_sid, auth_token)
    twilio_client.messages.create(
        from_=from_number,
        to=payload.phone,
        body=f"Seu acesso ao Sotel Fit Core foi liberado.\n\nAgora precisamos que voce complete seu cadastro inicial para montar seu plano personalizado.\n\nAcesse aqui:\n{ONBOARDING_LINK}"
    )
    return {"status": "success", "phone": payload.phone, "message": "Lead ativado e link de onboarding enviado"}


@router.post("/twilio/release-plan")
def release_plan(payload: ReleasePlanRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    state = db.query(ConversationState).filter(ConversationState.phone == payload.phone).first()
    if not state:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")
    state.status = "active"
    state.step = "active"
    db.commit()
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM")
    twilio_client = TwilioClient(account_sid, auth_token)
    twilio_client.messages.create(
        from_=from_number,
        to=payload.phone,
        body=f"Seu plano ja esta disponivel no Sotel Fit Core.\n\nAcesse aqui:\n{APP_LINK}"
    )
    return {"status": "success", "phone": payload.phone, "message": "Plano liberado e cliente avisado"}


@router.get("/leads")
def list_leads(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    leads = db.query(ConversationState).all()
    return [
        {
            "phone": l.phone,
            "name": l.name,
            "goal": l.goal,
            "routine": l.routine,
            "status": l.status,
            "step": l.step,
            "onboarding_link_sent": l.onboarding_link_sent,
            "created_at": l.created_at,
        }
        for l in leads
    ]


@router.get("/onboardings")
def list_onboardings(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    from models.lead_onboarding import LeadOnboarding
    onboardings = db.query(LeadOnboarding).order_by(LeadOnboarding.created_at.desc()).all()
    return [
        {
            "id": o.id, "phone": o.phone, "nome": o.nome, "email": o.email,
            "telefone": o.telefone, "idade": o.idade, "peso": o.peso, "altura": o.altura,
            "objetivo": o.objetivo, "nivel_treino": o.nivel_treino, "dias_treino": o.dias_treino,
            "horario_treino": o.horario_treino, "lesoes": o.lesoes, "alimentacao_atual": o.alimentacao_atual,
            "maior_dificuldade": o.maior_dificuldade, "meta_principal": o.meta_principal,
            "observacoes": o.observacoes, "created_at": o.created_at,
        }
        for o in onboardings
    ]


@router.get("/onboardings/by-phone/{phone}")
def get_onboarding_by_phone(phone: str, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    from models.lead_onboarding import LeadOnboarding
    o = db.query(LeadOnboarding).filter(LeadOnboarding.phone == phone).order_by(LeadOnboarding.created_at.desc()).first()
    if not o:
        return None
    return {
        "id": o.id, "phone": o.phone, "nome": o.nome, "email": o.email,
        "telefone": o.telefone, "idade": o.idade, "peso": o.peso, "altura": o.altura,
        "objetivo": o.objetivo, "nivel_treino": o.nivel_treino, "dias_treino": o.dias_treino,
        "horario_treino": o.horario_treino, "lesoes": o.lesoes, "alimentacao_atual": o.alimentacao_atual,
        "maior_dificuldade": o.maior_dificuldade, "meta_principal": o.meta_principal,
        "observacoes": o.observacoes, "created_at": o.created_at,
    }


@router.post("/clients/{client_id}/save-plan")
def save_client_plan(client_id: int, payload: dict, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    content = payload.get("content", "")
    db.execute(text("UPDATE client_plans SET status = 'inactive' WHERE client_id = :cid"), {"cid": client_id})
    db.execute(text("INSERT INTO client_plans (client_id, content, status, created_at) VALUES (:cid, :content, 'active', NOW())"), {"cid": client_id, "content": content})
    db.commit()
    return {"status": "ok", "message": "Plano salvo com sucesso"}


@router.post("/clients/{client_id}/save-diet")
def save_client_diet(client_id: int, payload: dict, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    content = payload.get("content", "")
    db.execute(text("UPDATE client_diets SET status = 'inactive' WHERE client_id = :cid"), {"cid": client_id})
    db.execute(text("INSERT INTO client_diets (client_id, content, status, created_at) VALUES (:cid, :content, 'active', NOW())"), {"cid": client_id, "content": content})
    db.commit()
    return {"status": "ok", "message": "Dieta salva com sucesso"}


@router.get("/clients")
def list_clients_admin(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    rows = db.execute(
        text("SELECT id, name, phone, objective, status FROM clients ORDER BY created_at DESC")
    ).fetchall()
    return [{"id": r[0], "name": r[1], "phone": r[2], "objective": r[3], "status": r[4]} for r in rows]
