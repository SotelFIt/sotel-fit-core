from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.client import Client
from models.onboarding import Onboarding
from models.diet import Diet
from services.diet_version_service import create_diet_version

def get_all_diets(db: Session):
    return db.query(Diet).all()

def get_diets_by_client_id(db: Session, client_id: int):
    return db.query(Diet).filter(Diet.client_id == client_id).all()

def _get_next_version_number(db: Session, client_id: int):
    from models.diet_version import DietVersion
    
    last_version = (
        db.query(DietVersion)
        .filter(DietVersion.client_id == client_id)
        .order_by(DietVersion.version_number.desc())
        .first()
    )
    return 1 if not last_version else last_version.version_number + 1

def create_diet(db: Session, diet_data):
    try:
        client = db.query(Client).filter(Client.id == diet_data.client_id).first()
        if not client:
            raise ValueError(f"Cliente com ID {diet_data.client_id} nao encontrado")
        
        onboarding = (
            db.query(Onboarding)
            .filter(Onboarding.id == diet_data.onboarding_id)
            .first()
        )
        if not onboarding:
            raise ValueError(f"Onboarding com ID {diet_data.onboarding_id} nao encontrado")
        
        if onboarding.client_id != diet_data.client_id:
            raise ValueError(f"Onboarding nao pertence ao cliente {diet_data.client_id}")
        
        existing_diet = (
            db.query(Diet)
            .filter(Diet.client_id == diet_data.client_id)
            .first()
        )
        if existing_diet:
            raise ValueError(f"Cliente {diet_data.client_id} ja possui uma dieta")
        
        new_diet = Diet(
            client_id=diet_data.client_id,
            onboarding_id=diet_data.onboarding_id,
            dietary_plan=diet_data.dietary_plan,
            observations=diet_data.observations,
        )
        
        db.add(new_diet)
        db.flush()
        
        version_number = _get_next_version_number(db, diet_data.client_id)
        create_diet_version(
            db=db,
            client_id=diet_data.client_id,
            diet_id=new_diet.id,
            version_number=version_number,
            dietary_plan=new_diet.dietary_plan,
            observations=new_diet.observations or "",
            change_reason="Dieta criada manualmente",
        )
        
        return new_diet
        
    except IntegrityError as e:
        db.rollback()
        raise ValueError("Erro de integridade ao criar dieta") from e
    except Exception as e:
        db.rollback()
        raise

def generate_automatic_diet(db: Session, client_id: int):
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError(f"Cliente com ID {client_id} nao encontrado")
        
        onboarding = (
            db.query(Onboarding)
            .filter(Onboarding.client_id == client_id)
            .order_by(Onboarding.id.desc())
            .first()
        )
        if not onboarding:
            raise ValueError(f"Nenhum onboarding encontrado para cliente {client_id}")
        
        existing_diet = db.query(Diet).filter(Diet.client_id == client_id).first()
        if existing_diet:
            return existing_diet
        
        goal = (onboarding.main_goal or "").lower()
        
        if "emagrec" in goal:
            dietary_plan = "Dieta com deficit calorico leve, 4 refeicoes, proteina alta, carboidrato controlado."
            observations = "Priorizar hidratacao e consistencia."
        
        elif "hipertrof" in goal or "massa" in goal:
            dietary_plan = "Dieta com superavit calorico controlado, 5 refeicoes, proteina alta, carboidratos elevados."
            observations = "Priorizar recuperacao e sono adequado."
        
        else:
            dietary_plan = "Dieta equilibrada com 4 refeicoes, foco em organizacao e adesao."
            observations = "Ajustar conforme resposta nas proximas semanas."
        
        new_diet = Diet(
            client_id=client_id,
            onboarding_id=onboarding.id,
            dietary_plan=dietary_plan,
            observations=observations,
        )
        
        db.add(new_diet)
        db.flush()
        
        version_number = _get_next_version_number(db, client_id)
        create_diet_version(
            db=db,
            client_id=client_id,
            diet_id=new_diet.id,
            version_number=version_number,
            dietary_plan=new_diet.dietary_plan,
            observations=new_diet.observations or "",
            change_reason="Dieta gerada automaticamente",
        )
        
        return new_diet
        
    except IntegrityError as e:
        db.rollback()
        raise ValueError("Erro de integridade ao gerar dieta") from e
    except Exception as e:
        db.rollback()
        raise

def regenerate_diet(db: Session, client_id: int):
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError(f"Cliente com ID {client_id} nao encontrado")
        
        onboarding = (
            db.query(Onboarding)
            .filter(Onboarding.client_id == client_id)
            .order_by(Onboarding.id.desc())
            .first()
        )
        if not onboarding:
            raise ValueError(f"Nenhum onboarding encontrado para cliente {client_id}")
        
        existing_diet = db.query(Diet).filter(Diet.client_id == client_id).first()
        if existing_diet:
            db.delete(existing_diet)
            db.flush()
        
        goal = (onboarding.main_goal or "").lower()
        
        if "emagrec" in goal:
            dietary_plan = "Dieta regenerada com deficit calorico leve, 4 refeicoes, proteina alta, carboidrato controlado."
            observations = "Priorizar hidratacao e consistencia."
        
        elif "hipertrof" in goal or "massa" in goal:
            dietary_plan = "Dieta regenerada com superavit calorico controlado, 5 refeicoes, proteina alta, carboidratos elevados."
            observations = "Priorizar recuperacao e sono adequado."
        
        else:
            dietary_plan = "Dieta regenerada equilibrada com 4 refeicoes, foco em organizacao e adesao."
            observations = "Ajustar conforme resposta nas proximas semanas."
        
        new_diet = Diet(
            client_id=client_id,
            onboarding_id=onboarding.id,
            dietary_plan=dietary_plan,
            observations=observations,
        )
        
        db.add(new_diet)
        db.flush()
        
        version_number = _get_next_version_number(db, client_id)
        create_diet_version(
            db=db,
            client_id=client_id,
            diet_id=new_diet.id,
            version_number=version_number,
            dietary_plan=new_diet.dietary_plan,
            observations=new_diet.observations or "",
            change_reason="Dieta regenerada automaticamente",
        )
        
        return new_diet
        
    except IntegrityError as e:
        db.rollback()
        raise ValueError("Erro de integridade ao regenerar dieta") from e
    except Exception as e:
        db.rollback()
        raise