from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import stripe
import os
import logging
from core.database import get_db
from core.phone import normalize_phone, normalize_phone_for_whatsapp
from services.twilio_service import send_whatsapp_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["Stripe"])

APP_LINK = "https://sotel-client.vercel.app/onboarding"


@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload invalido")
    except Exception:
        raise HTTPException(status_code=400, detail="Assinatura invalida")

    event_id = event.get("id")
    event_type = event.get("type")
    logger.info(f"Stripe webhook recebido: {event_type} id={event_id}")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]

        # Idempotencia — verificar se esse evento ja foi processado
        already = db.execute(
            text("SELECT 1 FROM stripe_events WHERE event_id = :eid LIMIT 1"),
            {"eid": event_id}
        ).fetchone()

        if already:
            logger.info(f"Stripe evento duplicado ignorado: {event_id}")
            return {"status": "duplicate", "event_id": event_id}

        # Registrar evento
        try:
            db.execute(
                text("INSERT INTO stripe_events (event_id, event_type, created_at) VALUES (:eid, :etype, NOW())"),
                {"eid": event_id, "etype": event_type}
            )
            db.commit()
        except Exception as e:
            logger.warning(f"Nao foi possivel registrar stripe_event: {e}")
            db.rollback()

        customer_details = session.get("customer_details") or {}
        customer_phone = customer_details.get("phone")

        if not customer_phone:
            logger.warning("Stripe webhook: phone nao encontrado no checkout")
            return {"status": "ignored", "reason": "phone not found"}

        phone_normalized = normalize_phone(customer_phone)
        phone_whatsapp = normalize_phone_for_whatsapp(customer_phone)

        # Atualizar status do cliente
        db.execute(
            text("UPDATE clients SET status = 'active' WHERE phone = :p"),
            {"p": phone_normalized}
        )
        db.commit()

        # Enviar WhatsApp
        message = (
            f"Seu acesso ao Sotel Fit Core foi liberado.\n\n"
            f"Agora precisamos que voce complete seu cadastro inicial "
            f"para montar seu plano personalizado.\n\n"
            f"Acesse aqui:\n{APP_LINK}"
        )
        send_whatsapp_message(phone_whatsapp, message)
        logger.info(f"Stripe checkout processado para {phone_normalized}")

    return {"status": "ok"}