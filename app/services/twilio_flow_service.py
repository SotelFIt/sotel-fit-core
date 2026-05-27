import logging
from sqlalchemy.orm import Session
from models.conversation_state import ConversationState
from services.ai_service import get_ai_response

logger = logging.getLogger(__name__)

APP_LINK = "https://sotel-client.vercel.app"
PLANS_LINK = "https://sotel-client.vercel.app/planos"

def generate_checkout_link(phone: str) -> str:
    try:
        import stripe
        import os
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        price_id = os.getenv("STRIPE_PRICE_ID")
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{APP_LINK}/onboarding?phone={phone}",
            cancel_url=APP_LINK,
            metadata={"phone": phone}
        )
        return session.url
    except Exception as e:
        logger.error(f"Erro ao gerar checkout para {phone}: {e}")
        return APP_LINK

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
    "Escolha seu plano aqui:\n\nhttps://sotel-client.vercel.app/planos\n\n"
    "Assim que o pagamento for confirmado, seu acesso ao app sera liberado."
        )

    if step == "waiting_payment":
        return (
            "Seu cadastro inicial ja esta salvo. "
            "Agora falta apenas confirmar o pagamento para liberar seu acesso ao app."
        )

    if step == "active_client":
        client_name = state.name
        logger.info(f"IA respondendo para cliente ativo {phone}: {incoming_msg[:50]}")
        return get_ai_response(message=incoming_msg, client_name=client_name)

    return "Nao entendi. Pode repetir?"