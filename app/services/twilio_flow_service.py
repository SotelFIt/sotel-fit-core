import logging
import requests
from sqlalchemy.orm import Session
from models.conversation_state import ConversationState
from services.ai_service import get_ai_response

logger = logging.getLogger(__name__)

BACKEND_URL = "https://sotel-fit-core-production-d98a.up.railway.app"
API_KEY = "c7c4205bdb3ae251c03436d1647f7cd5"
APP_LINK = "https://sotel-client.vercel.app"

def generate_checkout_link(phone: str) -> str:
    try:
        resp = requests.post(
            f"{BACKEND_URL}/stripe/create-checkout",
            json={"phone": phone},
            headers={"x-api-key": API_KEY},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("checkout_url", APP_LINK)
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
        checkout_url = generate_checkout_link(phone)
        return (
            "Show. Pelo que voce me passou, o proximo passo e ativar seu acesso "
            "ao metodo Sotel Personal Trainer.\n\n"
            f"Clique no link abaixo para fazer o pagamento:\n\n{checkout_url}\n\n"
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