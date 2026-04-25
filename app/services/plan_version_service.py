from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.plan_version import PlanVersion
from models.plan import Plan

def create_plan_version(
    db: Session,
    client_id: int,
    plan_id: int,
    version_number: int,
    training_plan: str,
    diet_plan: str,
    notes: str,
    change_reason: str = "Versão criada manualmente",
):
    """
    Cria uma nova versão de plano.
    
    Responsabilidades:
    - Validar plan_id existe
    - Criar snapshot do plano
    - Adicionar à sessão (SEM commit)
    - Tratar erros
    """
    
    try:
        # ✅ Validar se plan existe
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            raise ValueError(f"Plano com ID {plan_id} não encontrado")
        
        # ✅ Validar se client_id corresponde
        if plan.client_id != client_id:
            raise ValueError(f"Plano não pertence ao cliente {client_id}")
        
        # ✅ Criar snapshot (imutável)
        snapshot_json = {
            "training_plan": training_plan,
            "diet_plan": diet_plan,
            "notes": notes,
            "change_reason": change_reason,
        }
        
        # ✅ Criar versão
        new_version = PlanVersion(
            client_id=client_id,
            source_plan_id=plan_id,
            version_number=version_number,
            snapshot_json=snapshot_json,
        )
        
        # ✅ Apenas ADD (commit no service chamador)
        db.add(new_version)
        db.flush()
        
        return new_version
        
    except IntegrityError as e:
        db.rollback()
        raise ValueError("Erro de integridade ao criar versão de plano") from e
    except Exception as e:
        db.rollback()
        raise

def list_plan_versions_by_plan(db: Session, plan_id: int):
    """Lista todas as versões de um plano específico"""
    return (
        db.query(PlanVersion)
        .filter(PlanVersion.source_plan_id == plan_id)
        .order_by(PlanVersion.created_at.desc())
        .all()
    )

def list_plan_versions_by_client(db: Session, client_id: int):
    """Lista todas as versões de planos de um cliente"""
    return (
        db.query(PlanVersion)
        .filter(PlanVersion.client_id == client_id)
        .order_by(PlanVersion.created_at.desc())
        .all()
    )