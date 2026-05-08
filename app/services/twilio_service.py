import logging
import os
from twilio.rest import Client

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")


def normalize_phone(phone: str) -> str:
    p = phone.strip()
    if p.startswith("whatsapp:"):
        p = p.replace("whatsapp:", "")
    p = p.replace(" ", "").replace("-", "")
    if not p.startswith("+"):
        if p.startswith("55") and len(p) >= 12:
            p = "+" + p
        else:
            p = "+55" + p
    return p


def send_whatsapp_message(to_phone: str, message: str) -> bool:
    try:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            logger.error("Twilio credentials nao configuradas")
            return False

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        normalized = normalize_phone(to_phone)
        to = f"whatsapp:{normalized}"

        msg = client.messages.create(
            body=message,
            from_=TWILIO_FROM_NUMBER,
            to=to
        )
        logger.info(f"WhatsApp enviado para {to_phone} -> {to}: SID={msg.sid}")
        return True

    except Exception as e:
        logger.error(f"Erro ao enviar WhatsApp para {to_phone}: {e}")
        return False