from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.decision_log import DecisionLog
from models.checkin import Checkin
from models.client import Client

def create_decision_log(
    db: Session,
    client_id: int,
    checkin_id: int,
    decision: str,
    status: str,
    alerts: list,
    summary: str,
):
    """
    Cria um log de decisão para rastreamento de mudanças.
    
    Validações:
    - Client deve existir
    - Checkin deve existir
    
    Responsabilidades:
    - Validar FKs
    - Construir objeto
    - Adicionar à sessão (SEM commit)
    - Tratar erros
    """
    
    try:
        # ✅ Validar cliente
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError(f"Cliente com ID {client_id} não encontrado")
        
        # ✅ Validar checkin
        checkin = db.query(Checkin).filter(Checkin.id == checkin_id).first()
        if not checkin:
            raise ValueError(f"Checkin com ID {checkin_id} não encontrado")
        
        # ✅ Validar se checkin pertence ao cliente
        if checkin.client_id != client_id:
            raise ValueError(f"Checkin não pertence ao cliente {client_id}")
        
        # ✅ Criar log (alerts como string separada por |)
        log = DecisionLog(
            client_id=client_id,
            checkin_id=checkin_id,
            decision=decision,
            status=status,
            alerts=" | ".join(alerts) if alerts else "",
            summary=summary,
        )
        
        # ✅ Apenas ADD (commit no service chamador)
        db.add(log)
        db.flush()
        
        return log
        
    except IntegrityError as e:
        db.rollback()
        raise ValueError("Erro de integridade ao criar log de decisão") from e
    except Exception as e:
        db.rollback()
        raise

def get_decision_logs_by_client(db: Session, client_id: int):
    """Lista todos os logs de decisão de um cliente"""
    return db.query(DecisionLog).filter(DecisionLog.client_id == client_id).all()

def get_decision_logs_by_checkin(db: Session, checkin_id: int):
    """Lista todos os logs de decisão de um checkin"""
    return db.query(DecisionLog).filter(DecisionLog.checkin_id == checkin_id).all()