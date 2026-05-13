import logging
from sqlalchemy import text
from core.database import engine
from services.twilio_service import send_whatsapp_message

logger = logging.getLogger(__name__)

CLIENT_APP_URL = "https://sotel-client.vercel.app"


def send_workout_reminders():
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT id, phone, name FROM clients "
                "WHERE status IN ('active', 'active_client') "
                "AND phone IS NOT NULL "
                "AND (last_workout_reminder_sent IS NULL "
                "OR last_workout_reminder_sent < NOW() - INTERVAL '1 days') "
                "LIMIT 100"
            ))
            clients = result.fetchall()
            sent_count = 0

            for client_id, phone, name in clients:
                try:
                    first_name = (name or "").split()[0] if name else "cliente"
                    message = (
                        f"Ola {first_name}!\n\n"
                        f"Seu treino de hoje esta disponivel no Sotel Fit Core.\n\n"
                        f"Acesse: {CLIENT_APP_URL}\n\n"
                        f"Bora treinar!"
                    )

                    success = send_whatsapp_message(phone, message)

                    if success:
                        conn.execute(text(
                            "UPDATE clients SET last_workout_reminder_sent = NOW() WHERE id = :id"
                        ), {"id": client_id})
                        conn.commit()
                        sent_count += 1
                        logger.info(f"Lembrete treino enviado para {name} ({phone})")
                    else:
                        logger.warning(f"Falha ao enviar lembrete treino para {name} ({phone})")

                except Exception as e:
                    logger.error(f"Erro ao enviar lembrete treino para cliente {client_id}: {e}")
                    conn.rollback()

            logger.info(f"Lembretes treino enviados: {sent_count}/{len(clients)}")
            return {"sent": sent_count, "total": len(clients)}

    except Exception as e:
        logger.error(f"Erro em send_workout_reminders: {e}")
        return {"sent": 0, "total": 0, "error": str(e)}