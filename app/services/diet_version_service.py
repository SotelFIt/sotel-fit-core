from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.diet_version import DietVersion
from models.diet import Diet

def create_diet_version(
    db: Session,
    client_id: int,
    diet_id: int,
    version_number: int,
    dietary_plan: str,
    observations: str,
    change_reason: str = "Versao criada manualmente",
):
    try:
        diet = db.query(Diet).filter(Diet.id == diet_id).first()
        if not diet:
            raise ValueError(f"Dieta com ID {diet_id} nao encontrada")
        
        if diet.client_id != client_id:
            raise ValueError(f"Dieta nao pertence ao cliente {client_id}")
        
        snapshot_json = {
            "dietary_plan": dietary_plan,
            "observations": observations,
            "change_reason": change_reason,
        }
        
        new_version = DietVersion(
            client_id=client_id,
            source_diet_id=diet_id,
            version_number=version_number,
            snapshot_json=snapshot_json,
        )
        
        db.add(new_version)
        db.flush()
        
        return new_version
        
    except IntegrityError as e:
        db.rollback()
        raise ValueError("Erro de integridade ao criar versao") from e
    except Exception as e:
        db.rollback()
        raise

def list_diet_versions_by_diet(db: Session, diet_id: int):
    return (
        db.query(DietVersion)
        .filter(DietVersion.source_diet_id == diet_id)
        .order_by(DietVersion.created_at.desc())
        .all()
    )

def list_diet_versions_by_client(db: Session, client_id: int):
    return (
        db.query(DietVersion)
        .filter(DietVersion.client_id == client_id)
        .order_by(DietVersion.created_at.desc())
        .all()
    )