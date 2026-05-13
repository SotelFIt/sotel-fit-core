from sqlalchemy.orm import Session
from sqlalchemy import text
from core.phone import normalize_phone
import logging

logger = logging.getLogger(__name__)


def get_or_create_client_from_phone(db: Session, phone: str, name: str = None) -> dict:
    normalized = normalize_phone(phone)

    row = db.execute(
        text("SELECT id, name, phone, objective, status FROM clients WHERE phone = :p LIMIT 1"),
        {"p": normalized}
    ).fetchone()

    if row:
        if name and name != row[1]:
            db.execute(
                text("UPDATE clients SET name = :name WHERE phone = :p"),
                {"name": name, "p": normalized}
            )
            db.commit()
        return {"id": row[0], "name": name or row[1], "phone": row[2], "objective": row[3], "status": row[4]}

    result = db.execute(
        text("INSERT INTO clients (name, phone, status, created_at) VALUES (:name, :phone, 'lead', NOW()) RETURNING id, name, phone, objective, status"),
        {"name": name or "Cliente WhatsApp", "phone": normalized}
    ).fetchone()
    db.commit()
    logger.info(f"Cliente criado automaticamente: {normalized}")
    return {"id": result[0], "name": result[1], "phone": result[2], "objective": result[3], "status": result[4]}


def fix_orphan_conversation_states(db: Session):
    orphans = db.execute(
        text("SELECT cs.phone, cs.name FROM conversation_states cs WHERE cs.phone IS NOT NULL AND NOT EXISTS (SELECT 1 FROM clients c WHERE c.phone = cs.phone)")
    ).fetchall()

    count = 0
    for row in orphans:
        try:
            normalized = normalize_phone(row[0])
            db.execute(
                text("INSERT INTO clients (name, phone, status, created_at) VALUES (:name, :phone, 'lead', NOW()) ON CONFLICT DO NOTHING"),
                {"name": row[1] or "Lead WhatsApp", "phone": normalized}
            )
            count += 1
        except Exception as e:
            logger.warning(f"Erro ao criar client para {row[0]}: {e}")
            db.rollback()

    if count > 0:
        db.commit()
        logger.info(f"fix_orphan_conversation_states: {count} clientes criados")
    return count