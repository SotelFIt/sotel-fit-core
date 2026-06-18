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


@router.get("/twilio-send-test/{phone}")
def twilio_send_test(phone: str, vars: int = 0):
    from twilio.rest import Client as TwilioClient
    import json as _json
    try:
        c = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        from routers.admin import get_twilio_from, whatsapp_to, APP_LINK
        kwargs = {
            "from_": get_twilio_from(),
            "to": whatsapp_to(phone),
            "content_sid": os.getenv("TWILIO_TEMPLATE_PLANO"),
        }
        if vars >= 1:
            kwargs["content_variables"] = _json.dumps({"1": "Fernando", "2": "https://sotel-client.vercel.app"})
        if vars == 2:
            kwargs["status_callback"] = os.getenv("PUBLIC_BACKEND_URL", "").rstrip("/") + "/webhook/twilio-status"
        if vars == 3:
            return {"debug": True, "helper_to": whatsapp_to(phone), "fixed_to": "whatsapp:+" + phone, "from": get_twilio_from()}
        m = c.messages.create(**kwargs)
        return {"ok": True, "sid": m.sid, "status": m.status, "vars_sent": vars}
    except Exception as e:
        return {
            "ok": False, "vars_sent": vars,
            "code": getattr(e, "code", None),
            "msg": getattr(e, "msg", None),
            "details": getattr(e, "details", None),
            "raw": str(e),
        }


@router.get("/twilio-fetch-debug/{sid}")
def twilio_fetch_debug(sid: str):
    from twilio.rest import Client as TwilioClient
    try:
        c = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        m = c.messages(sid).fetch()
        return {
            "sid": m.sid,
            "status": m.status,
            "error_code": m.error_code,
            "error_message": m.error_message,
            "to": m.to,
            "from": m.from_,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/twilio-status-debug")
def twilio_status_debug():
    return {
        "public_backend_url_present": bool(os.getenv("PUBLIC_BACKEND_URL")),
        "public_backend_url_len": len(os.getenv("PUBLIC_BACKEND_URL", "")),
        "twilio_auth_token_present": bool(os.getenv("TWILIO_AUTH_TOKEN")),
        "template_plano_present": bool(os.getenv("TWILIO_TEMPLATE_PLANO")),
        "template_plano_len": len(os.getenv("TWILIO_TEMPLATE_PLANO", "")),
        "from_number_env": os.getenv("TWILIO_FROM_NUMBER"),
        "whatsapp_from_env": os.getenv("TWILIO_WHATSAPP_FROM"),
        "module_level_public_url_len": len(PUBLIC_BACKEND_URL),
        "module_level_token_present": bool(TWILIO_AUTH_TOKEN),
    }


@router.post("/twilio-status")
async def twilio_status_callback(request: Request):
    form = await request.form()
    params = dict(form)

    signature = request.headers.get("X-Twilio-Signature", "")
    callback_url = PUBLIC_BACKEND_URL.rstrip("/") + "/webhook/twilio-status"

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
