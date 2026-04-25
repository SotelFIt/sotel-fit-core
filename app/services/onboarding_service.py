from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.onboarding import Onboarding
from models.client import Client

def create_onboarding(db: Session, onboarding_data):
    """
    Cria um novo onboarding para um cliente.
    
    Validações:
    - Client deve existir
    - Dados devem ser válidos
    
    Responsabilidades do service:
    - Validar client_id
    - Construir objeto
    - Adicionar à sessão (NÃO fazer commit)
    - Tratar erros
    """
    
    try:
        # ✅ Validar se cliente existe
        client = db.query(Client).filter(Client.id == onboarding_data.client_id).first()
        if not client:
            raise ValueError(f"Cliente com ID {onboarding_data.client_id} não encontrado")
        
        # ✅ Criar onboarding
        new_onboarding = Onboarding(
            client_id=onboarding_data.client_id,
            main_goal=onboarding_data.main_goal,
            training_level=onboarding_data.training_level,
            injuries=onboarding_data.injuries,
            routine=onboarding_data.routine,
            current_eating=onboarding_data.current_eating,
            difficulties=onboarding_data.difficulties,
            motivation=onboarding_data.motivation,
        )
        
        # ✅ Apenas ADD (commit fica para o router)
        db.add(new_onboarding)
        db.flush()  # Força geração de ID sem commit
        
        return new_onboarding
        
    except IntegrityError as e:
        db.rollback()
        raise ValueError("Erro de integridade ao criar onboarding") from e
    except Exception as e:
        db.rollback()
        raise

def get_all_onboarding(db: Session):
    """Retorna todos os onboardings"""
    return db.query(Onboarding).all()

def get_onboarding_by_client_id(db: Session, client_id: int):
    """Retorna onboardings de um cliente específico"""
    return db.query(Onboarding).filter(Onboarding.client_id == client_id).all()