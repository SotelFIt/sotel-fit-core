from fastapi import APIRouter, Request, HTTPException
from fastapi import Depends
from sqlalchemy.orm import Session
import stripe
import os
from twilio.rest import Client as TwilioClient
from core.database import get_db
from models.conversation_state import ConversationState

router = APIRouter(prefix="/webhook", tags=["Stripe"])

APP_LINK = "https://frontend-iota-rose-78.vercel.app/onboarding"

@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido")
    except Exception:
        raise HTTPException(status_code=400, detail="Assinatura inválida")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_details = session.get("customer_details") or {}
        customer_phone = customer_details.get("phone")

        if not customer_phone:
            return {"status": "ignored", "reason": "phone not found"}

        phone = f"whatsapp:{customer_phone}"
        state = db.query(ConversationState).filter(ConversationState.phone == phone).first()

        if state:
            state.status = "active_client"
            state.step = "active_client"
            db.commit()

            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            from_number = os.getenv("TWILIO_WHATSAPP_FROM")

            twilio_client = TwilioClient(account_sid, auth_token)
            twilio_client.messages.create(
                from_=from_number,
                to=phone,
                body=f"Seu acesso ao Sotel Fit Core foi liberado.\n\nAgora precisamos que você complete seu cadastro inicial para montar seu plano personalizado.\n\nAcesse aqui:\n{APP_LINK}"
            )

    return {"status": "ok"}