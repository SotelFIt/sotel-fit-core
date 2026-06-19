import os
import logging
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import text
from twilio.request_validator import RequestValidator
from core.database import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["Twilio"])

PUBLIC_BACKEND_URL = os.getenv("PUBLIC_BACKEND_URL", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")


@router.post("/twilio-status")
async def twilio_status_callback(request: Request):
    form = await request.form()
    params = dict(form)

    signature = request.headers.get("X-Twilio-Signature", "")
    callback_url = PUBLIC_BACKEND_URL.strip().rstrip("/") + "/webhook/twilio-status"

    if not PUBLIC_BACKEND_URL or not TWILIO_AUTH_TOKEN:
        logger.error("twilio-status: PUBLIC_BACKEND_URL ou TWILIO_AUTH_TOKEN ausente - rejeitando")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="callback nao configurado")

    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    if not validator.validate(callback_url, params, signature):
        logger.warning("twilio-status: assinatura invalida")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="assinatura invalida")

    message_sid = params.get("MessageSid") or params.get("SmsSid")
    message_status = params.get("MessageStatus") or params.get("SmsStatus")
    error_code = params.get("ErrorCode")

    if not message_sid or not message_status:
        return Response(status_code=204)

    db = SessionLocal()
    try:
        db.execute(
            text("UPDATE whatsapp_events SET status = :st, error_code = :ec, updated_at = NOW() WHERE message_sid = :sid"),
            {"st": message_status, "ec": error_code, "sid": message_sid}
        )
        db.commit()
        logger.info("twilio-status: sid=" + str(message_sid) + " status=" + str(message_status) + " error=" + str(error_code))
    except Exception as e:
        db.rollback()
        logger.error("twilio-status: erro ao atualizar whatsapp_events: " + str(e))
    finally:
        db.close()

    return Response(status_code=204)
