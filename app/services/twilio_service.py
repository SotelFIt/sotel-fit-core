import logging
import os
from twilio.rest import Client

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")


def send_whatsapp_message(to_phone: str, message: str) -> bool:
    try:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            logger.error("Twilio credentials nao configuradas")
            return False

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        to = to_phone.strip()
        if not to.startswith("whatsapp:"):
            if not to.startswith("+"):
                to = "+" + to
            to = f"whatsapp:{to}"

        msg = client.messages.create(
            body=message,
            from_=TWILIO_FROM_NUMBER,
            to=to
        )
        logger.info(f"WhatsApp enviado para {to_phone}: SID={msg.sid}")
        return True

    except Exception as e:
        logger.error(f"Erro ao enviar WhatsApp para {to_phone}: {e}")
        return False