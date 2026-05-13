from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import stripe
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stripe", tags=["Stripe Checkout"])

APP_URL = "https://sotel-client.vercel.app"


class CheckoutRequest(BaseModel):
    phone: str


@router.post("/create-checkout")
def create_checkout(data: CheckoutRequest):
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    price_id = os.getenv("STRIPE_PRICE_ID")

    logger.info(f"STRIPE_SECRET_KEY presente: {bool(stripe.api_key)}")
    logger.info(f"STRIPE_PRICE_ID presente: {bool(price_id)}")

    if not stripe.api_key or not price_id:
        raise HTTPException(status_code=500, detail=f"Stripe nao configurado: key={bool(stripe.api_key)} price={bool(price_id)}")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"phone": data.phone},
            success_url=f"{APP_URL}/onboarding?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{APP_URL}/planos?canceled=true",
            phone_number_collection={"enabled": True},
        )
        logger.info(f"Checkout criado para {data.phone}: {session.id}")
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error(f"Erro ao criar checkout: {e}")
        raise HTTPException(status_code=500, detail=str(e))