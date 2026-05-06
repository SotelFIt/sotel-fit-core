import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from core.database import engine
from services.twilio_service import send_whatsapp_message

logger = logging.getLogger(__name__)

def send_checkin_reminders():
    """Envia lembrete de check-in para clientes ativos."""
    
    try:
        with engine.connect() as conn:
            # Busca clientes ativos que não receberam lembrete nessa semana
            result = conn.execute(text("""
                SELECT id, phone, name
                FROM clients
                WHERE status IN ('active', 'active_client')
                AND (last_checkin_reminder_sent IS NULL OR last_checkin_reminder_sent < NOW() - INTERVAL '7 days')
                LIMIT 100
            """))
            
            clients = result.fetchall()
            sent_count = 0
            
            for client_id, phone, name in clients:
                try:
                    # Envia mensagem
                    message = f"""Olá {name}! 👋

Já respondeu seu **check-in semanal** no Sotel Fit Core?

Acesse: https://frontend-iota-rose-78.vercel.app/checkin

Suas respostas ajudam seu treinador a ajustar melhor seu treino e dieta! 💪"""
                    
                    send_whatsapp_message(phone, message)
                    
                    # Atualiza timestamp
                    conn.execute(text("""
                        UPDATE clients
                        SET last_checkin_reminder_sent = NOW()
                        WHERE id = :id
                    """), {"id": client_id})
                    conn.commit()
                    
                    sent_count += 1
                    logger.info(f"Lembrete enviado para {name} ({phone})")
                    
                except Exception as e:
                    logger.error(f"Erro ao enviar lembrete para cliente {client_id}: {e}")
                    conn.rollback()
            
            logger.info(f"Lembretes enviados: {sent_count}/{len(clients)}")
            return {"sent": sent_count, "total": len(clients)}
            
    except Exception as e:
        logger.error(f"Erro em send_checkin_reminders: {e}")
        return {"sent": 0, "total": 0, "error": str(e)}