import logging
from sqlalchemy.orm import Session
from models.conversation_state import ConversationState
from core.phone import normalize_phone_for_whatsapp

logger = logging.getLogger(__name__)

PAYMENT_LINK = "https://buy.stripe.com/test_dRm4gzc9haB32Im4e7fbq00"
APP_LINK = "https://sotel-client.vercel.app"


def handle_twilio_flow(phone: str, incoming_msg: str, db: Session) -> str:
    if not phone:
        return "Erro: telefone nao identificado."

    state = db.query(ConversationState).filter(
        ConversationState.phone == phone
    ).first()

    if not state:
        state = ConversationState(phone=phone, step="start")
        db.add(state)
        db.commit()
        db.refresh(state)

    step = state.step

    if step == "start":
        state.step = "ask_name"
        db.commit()
        return "Fala! Eu sou o assistente da Sotel Personal Trainer. Qual seu nome?"

    if step == "ask_name":
        state.name = incoming_msg.strip()
        state.step = "ask_goal"
        db.commit()
        return (
            f"Prazer, {state.name}! Qual seu objetivo hoje?\n"
            "1 - Emagrecimento\n"
            "2 - Ganho de massa\n"
            "3 - Condicionamento\n"
            "4 - Melhorar saude e rotina"
        )

    if step == "ask_goal":
        state.goal = incoming_msg.strip()
        state.step = "ask_routine"
        db.commit()
        return "Perfeito. Quantos dias por semana voce consegue treinar?"

    if step == "ask_routine":
        state.routine = incoming_msg.strip()
        state.step = "waiting_payment"
        db.commit()
        return (
            "Show. Pelo que voce me passou, o proximo passo e ativar seu acesso "
            "ao metodo Sotel Personal Trainer.\n\n"
            f"Clique no link abaixo para fazer o pagamento:\n\n{PAYMENT_LINK}\n\n"
            "Assim que o pagamento for confirmado, seu acesso ao app sera liberado."
        )

    if step == "waiting_payment":
        return (
            "Seu cadastro inicial ja esta salvo. "
            "Agora falta apenas confirmar o pagamento para liberar seu acesso ao app."
        )

    if step == "active_client":
        return f"Seu acesso ja esta liberado. Acesse seu painel aqui:\n{APP_LINK}"

    return "Nao entendi. Pode repetir?"