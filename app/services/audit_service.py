import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def audit_log(db: Session, action: str, client_id: int = None, admin_id: int = None, details: str = None):
    try:
        db.execute(
            text(
                "INSERT INTO admin_audit_log (action, admin_id, client_id, details, created_at) "
                "VALUES (:action, :admin_id, :client_id, :details, NOW())"
            ),
            {
                "action": action,
                "admin_id": admin_id,
                "client_id": client_id,
                "details": details,
            }
        )
        db.commit()
        logger.info(f"AUDIT: {action} client_id={client_id} admin_id={admin_id} details={details}")
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar audit_log: {e}")