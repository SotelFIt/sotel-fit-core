"""
Client Service
Funções centrais para criação e recuperação de clientes.
Regra: todo telefone que entra no sistema deve ter um registro em clients.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    """Normaliza telefone para formato whatsapp:+55XXXXXXXXXXX"""
    if phone.startswith("whatsapp:"):
        return phone
    digits = ''.join(filter(str.isdigit, phone))
    if not digits.startswith("55"):
        digits = "55" + digits
    return f"whatsapp:+{digits}"


def get_or_create_client_from_phone(db: Session, phone: str, name: str = None) -> dict:
    """
    Busca ou cria um cliente pelo telefone.
    Garante que todo telefone tenha um registro em clients.
    """
    normalized = normalize_phone(phone)

    # Buscar cliente existente
    row = db.execute(
        text("SELECT id, name, phone, objective, status FROM clients WHERE phone = :p LIMIT 1"),
        {"p": normalized}
    ).fetchone()

    if row:
        # Atualizar nome se veio um novo
        if name and name != row[1]:
            db.execute(
                text("UPDATE clients SET name = :name WHERE phone = :p"),
                {"name": name, "p": normalized}
            )
            db.commit()
        return {"id": row[0], "name": name or row[1], "phone": row[2], "objective": row[3], "status": row[4]}

    # Criar novo cliente
    result = db.execute(
        text("""
            INSERT INTO clients (name, phone, status, created_at)
            VALUES (:name, :phone, 'lead', NOW())
            RETURNING id, name, phone, objective, status
        """),
        {"name": name or "Cliente WhatsApp", "phone": normalized}
    ).fetchone()
    db.commit()

    logger.info(f"Cliente criado automaticamente: {normalized}")
    return {"id": result[0], "name": result[1], "phone": result[2], "objective": result[3], "status": result[4]}


def fix_orphan_conversation_states(db: Session):
    """
    Corrige conversation_states que não têm client correspondente.
    Cria um client para cada telefone órfão.
    """
    orphans = db.execute(
        text("""
            SELECT cs.phone, cs.name
            FROM conversation_states cs
            WHERE cs.phone IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM clients c WHERE c.phone = cs.phone
            )
        """)
    ).fetchall()

    count = 0
    for row in orphans:
        try:
            db.execute(
                text("""
                    INSERT INTO clients (name, phone, status, created_at)
                    VALUES (:name, :phone, 'lead', NOW())
                    ON CONFLICT DO NOTHING
                """),
                {"name": row[1] or "Lead WhatsApp", "phone": row[0]}
            )
            count += 1
        except Exception as e:
            logger.warning(f"Erro ao criar client para {row[0]}: {e}")
            db.rollback()

    if count > 0:
        db.commit()
        logger.info(f"fix_orphan_conversation_states: {count} clientes criados")

    return count
