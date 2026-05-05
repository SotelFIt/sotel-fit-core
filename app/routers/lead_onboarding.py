from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import os
from twilio.rest import Client as TwilioClient
from core.database import get_db
from models.lead_onboarding import LeadOnboarding
from models.conversation_state import ConversationState
from models.client import Client

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
    phone_formatted = None
    if payload.telefone:
        digits = ''.join(filter(str.isdigit, payload.telefone))
        if not digits.startswith('55'):
            digits = '55' + digits
        phone_formatted = f"whatsapp:+{digits}"

    # Salvar onboarding
    onboarding = LeadOnboarding(
        phone=phone_formatted,
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

    # Atualizar ConversationState se existir
    if phone_formatted:
        state = db.query(ConversationState).filter(
            ConversationState.phone == phone_formatted
        ).first()
        if state:
            state.status = "onboarding_completed"
            state.step = "onboarding_completed"

    # Criar ou atualizar Client por telefone
    if phone_formatted:
        client = db.query(Client).filter(Client.phone == phone_formatted).first()
        if not client:
            client = Client(
                name=payload.nome or "Cliente",
                email=payload.email,
                phone=phone_formatted,
                objective=payload.objetivo,
                status="onboarding_completed",
                age=int(payload.idade) if payload.idade and payload.idade.isdigit() else None,
                weight=float(payload.peso) if payload.peso else None,
                height=float(payload.altura) if payload.altura else None,
            )
            db.add(client)
        else:
            client.name = payload.nome or client.name
            client.email = payload.email or client.email
            client.objective = payload.objetivo or client.objective
            client.status = "onboarding_completed"

    db.commit()

    # Enviar WhatsApp de confirmação
    if phone_formatted:
        try:
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            from_number = os.getenv("TWILIO_WHATSAPP_FROM")
            twilio_client = TwilioClient(account_sid, auth_token)
            twilio_client.messages.create(
                from_=from_number,
                to=phone_formatted,
                body="Cadastro recebido!\n\nAgora vamos montar seu plano personalizado com base nas suas respostas.\n\nAssim que estiver pronto, voce sera avisado aqui no WhatsApp."
            )
        except Exception:
            pass

    return {"status": "ok", "message": "Onboarding recebido com sucesso"}
