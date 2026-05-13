from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
import os
from twilio.rest import Client as TwilioClient
from core.database import get_db
from core.phone import normalize_phone, normalize_phone_for_whatsapp
from models.lead_onboarding import LeadOnboarding
from models.conversation_state import ConversationState

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


class LeadOnboardingRequest(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    idade: Optional[str] = None
    peso: Optional[str] = None
    altura: Optional[str] = None
    objetivo: Optional[str] = None
    nivel_treino: Optional[str] = None
    dias_treino: Optional[str] = None
    horario_treino: Optional[str] = None
    lesoes: Optional[str] = None
    alimentacao_atual: Optional[str] = None
    maior_dificuldade: Optional[str] = None
    meta_principal: Optional[str] = None
    observacoes: Optional[str] = None


@router.post("/lead")
def create_lead_onboarding(payload: LeadOnboardingRequest, db: Session = Depends(get_db)):
    phone_normalized = None
    phone_whatsapp = None

    if payload.telefone:
        phone_normalized = normalize_phone(payload.telefone)
        phone_whatsapp = normalize_phone_for_whatsapp(payload.telefone)

    onboarding = LeadOnboarding(
        phone=phone_normalized,
        nome=payload.nome,
        email=payload.email,
        telefone=payload.telefone,
        idade=payload.idade,
        peso=payload.peso,
        altura=payload.altura,
        objetivo=payload.objetivo,
        nivel_treino=payload.nivel_treino,
        dias_treino=payload.dias_treino,
        horario_treino=payload.horario_treino,
        lesoes=payload.lesoes,
        alimentacao_atual=payload.alimentacao_atual,
        maior_dificuldade=payload.maior_dificuldade,
        meta_principal=payload.meta_principal,
        observacoes=payload.observacoes,
    )
    db.add(onboarding)

    if phone_whatsapp:
        state = db.query(ConversationState).filter(
            ConversationState.phone == phone_whatsapp
        ).first()
        if state:
            state.status = "onboarding_completed"
            state.step = "onboarding_completed"

    if phone_normalized:
        existing = db.execute(
            text("SELECT id FROM clients WHERE phone = :p LIMIT 1"),
            {"p": phone_normalized}
        ).fetchone()
        if not existing:
            db.execute(
                text("INSERT INTO clients (name, phone, status, email, objective, created_at, updated_at) VALUES (:name, :phone, 'onboarding_completed', NULL, :objective, NOW(), NOW())"),
                {"name": payload.nome or "Cliente", "phone": phone_normalized, "objective": payload.objetivo}
            )
        else:
            db.execute(
                text("UPDATE clients SET status = 'onboarding_completed', objective = :obj WHERE phone = :p"),
                {"obj": payload.objetivo, "p": phone_normalized}
            )

    db.commit()

    if phone_whatsapp:
        try:
            twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
            twilio_client.messages.create(
                from_=os.getenv("TWILIO_WHATSAPP_FROM"),
                to=phone_whatsapp,
                body="Cadastro recebido!\n\nAgora vamos montar seu plano personalizado.\n\nAssim que estiver pronto, voce sera avisado aqui no WhatsApp."
            )
        except Exception:
            pass

    return {"status": "ok", "message": "Onboarding recebido com sucesso"}