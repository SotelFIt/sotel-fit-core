"""
Landbot Service
Lógica de criação de clientes com idempotência
"""

from sqlalchemy.orm import Session
from schemas.landbot import LandbotRequestSchema
from models.client import Client


def create_client_idempotent(
    db: Session,
    landbot_user_id: str,
    name: str,
    phone: str,
    email: str,
    objective: str,
    difficulty: str
) -> Client:
    """
    Cria cliente ou retorna existente (idempotência)
    
    Verifica se cliente com mesmo landbot_user_id já existe.
    Se existir, retorna o cliente existente.
    Se não, cria novo cliente.
    """
    
    # Verificar se cliente já existe por landbot_user_id
    existing_client = db.query(Client).filter(
        Client.landbot_user_id == landbot_user_id
    ).first()
    
    if existing_client:
        return existing_client
    
    # Verificar se email já existe
    email_exists = db.query(Client.id).filter(
        Client.email == email
    ).first() is not None
    
    if email_exists:
        raise ValueError(f"Email '{email}' já cadastrado")
    
    # Criar cliente novo
    client = Client(
        name=name,
        email=email,
        phone=phone,
        objective=objective,
        difficulty=difficulty,
        landbot_user_id=landbot_user_id
    )
    
    db.add(client)
    db.commit()
    db.refresh(client)
    
    return client