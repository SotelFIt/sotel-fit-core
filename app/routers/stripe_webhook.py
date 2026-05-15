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

ONBOARDING_LINK = "https://sotel-client.vercel.app/onboarding"


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

    if event_type in ("checkout.session.completed", "invoice.payment_succeeded"):
        session = event["data"]["object"]

        already = db.execute(
            text("SELECT 1 FROM stripe_events WHERE event_id = :eid LIMIT 1"),
            {"eid": event_id}
        ).fetchone()

        if already:
            logger.info(f"Stripe evento duplicado ignorado: {event_id}")
            return {"status": "duplicate", "event_id": event_id}

        try:
            db.execute(
                text("INSERT INTO stripe_events (event_id, event_type, created_at) VALUES (:eid, :etype, NOW())"),
                {"eid": event_id, "etype": event_type}
            )
            db.commit()
        except Exception as e:
            logger.warning(f"Nao foi possivel registrar stripe_event: {e}")
            db.rollback()

        metadata = session.get("metadata") or {}
        customer_details = session.get("customer_details") or {}

        customer_phone = metadata.get("phone") or customer_details.get("phone")
        customer_email = customer_details.get("email") or metadata.get("email")
        customer_name = customer_details.get("name") or metadata.get("name") or "Cliente"

        if not customer_phone and not customer_email:
            logger.warning(f"Stripe webhook: phone e email nao encontrados. event_id={event_id}")
            return {"status": "ignored", "reason": "phone and email not found"}

        phone_normalized = normalize_phone(customer_phone) if customer_phone else None
        phone_whatsapp = normalize_phone_for_whatsapp(customer_phone) if customer_phone else None

        # Buscar cliente existente por phone ou email
        client_row = None
        if phone_normalized:
            client_row = db.execute(
                text("SELECT id FROM clients WHERE phone = :p LIMIT 1"),
                {"p": phone_normalized}
            ).fetchone()
        if not client_row and customer_email:
            client_row = db.execute(
                text("SELECT id FROM clients WHERE email = :e LIMIT 1"),
                {"e": customer_email}
            ).fetchone()

        if client_row:
            client_id = client_row[0]
            db.execute(
                text("""
                    UPDATE clients SET
                        status = 'active',
                        email = COALESCE(email, :email),
                        name = COALESCE(NULLIF(name, ''), :name),
                        phone = COALESCE(phone, :phone),
                        updated_at = NOW()
                    WHERE id = :cid
                """),
                {"email": customer_email, "name": customer_name, "phone": phone_normalized, "cid": client_id}
            )
            db.commit()
            logger.info(f"Cliente {client_id} atualizado para status active")
        else:
            result = db.execute(
                text("""
                    INSERT INTO clients (name, phone, email, status, created_at, updated_at)
                    VALUES (:name, :phone, :email, 'active', NOW(), NOW())
                    RETURNING id
                """),
                {"name": customer_name, "phone": phone_normalized, "email": customer_email}
            )
            db.commit()
            client_id = result.fetchone()[0]
            logger.info(f"Novo cliente criado via Stripe: id={client_id}")

        # Ativar assinatura automaticamente
        try:
            existing_sub = db.execute(
                text("SELECT id FROM subscriptions WHERE client_id = :cid LIMIT 1"),
                {"cid": client_id}
            ).fetchone()

            if existing_sub:
                db.execute(
                    text("""
                        UPDATE subscriptions SET
                            status = 'active',
                            plan_type = 'monthly',
                            payment_status = 'paid',
                            manual_payment_method = 'stripe',
                            start_date = NOW(),
                            end_date = NOW() + INTERVAL '30 days',
                            last_payment_date = NOW(),
                            next_payment_date = NOW() + INTERVAL '30 days',
                            updated_at = NOW()
                        WHERE client_id = :cid
                    """),
                    {"cid": client_id}
                )
            else:
                db.execute(
                    text("""
                        INSERT INTO subscriptions (
                            client_id, status, plan_type, payment_status,
                            manual_payment_method, start_date, end_date,
                            last_payment_date, next_payment_date, created_at, updated_at
                        ) VALUES (
                            :cid, 'active', 'monthly', 'paid',
                            'stripe', NOW(), NOW() + INTERVAL '30 days',
                            NOW(), NOW() + INTERVAL '30 days', NOW(), NOW()
                        )
                    """),
                    {"cid": client_id}
                )
            db.commit()
            logger.info(f"Assinatura ativada automaticamente para cliente {client_id}")
        except Exception as e:
            logger.error(f"Erro ao ativar assinatura: {e}")
            db.rollback()

        # Enviar WhatsApp
        if phone_whatsapp:
            message = (
                f"Pagamento confirmado! Bem-vindo ao Sotel Fit Core.\n\n"
                f"Agora complete seu cadastro inicial para que seu plano personalizado seja montado.\n\n"
                f"Acesse aqui:\n{ONBOARDING_LINK}"
            )
            try:
                send_whatsapp_message(phone_whatsapp, message)
                logger.info(f"WhatsApp enviado para {phone_whatsapp}")
            except Exception as e:
                logger.error(f"Erro ao enviar WhatsApp: {e}")

        logger.info(f"Stripe {event_type} processado para cliente {client_id}")

    return {"status": "ok"}