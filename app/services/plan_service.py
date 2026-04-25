from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.client import Client
from models.onboarding import Onboarding
from models.plan import Plan
from services.plan_version_service import create_plan_version

def get_all_plans(db: Session):
    """Retorna todos os planos"""
    return db.query(Plan).all()

def get_plans_by_client_id(db: Session, client_id: int):
    """Retorna planos de um cliente específico"""
    return db.query(Plan).filter(Plan.client_id == client_id).all()

def _get_next_version_number(db: Session, client_id: int):
    """Calcula o próximo número de versão para um cliente"""
    from models.plan_version import PlanVersion
    
    last_version = (
        db.query(PlanVersion)
        .filter(PlanVersion.client_id == client_id)
        .order_by(PlanVersion.version_number.desc())
        .first()
    )
    return 1 if not last_version else last_version.version_number + 1

def create_plan(db: Session, plan_data):
    """
    Cria um novo plano para um cliente.
    
    Validações:
    - Client deve existir
    - Onboarding deve existir e pertencer ao cliente
    - Cliente não pode ter plano ativo
    
    Responsabilidades do service:
    - Validar FKs
    - Construir objeto
    - Criar versão inicial
    - Adicionar à sessão (SEM commit)
    - Tratar erros
    """
    
    try:
        # ✅ Validar cliente
        client = db.query(Client).filter(Client.id == plan_data.client_id).first()
        if not client:
            raise ValueError(f"Cliente com ID {plan_data.client_id} não encontrado")
        
        # ✅ Validar onboarding
        onboarding = (
            db.query(Onboarding)
            .filter(Onboarding.id == plan_data.onboarding_id)
            .first()
        )
        if not onboarding:
            raise ValueError(f"Onboarding com ID {plan_data.onboarding_id} não encontrado")
        
        # ✅ Validar se onboarding pertence ao cliente
        if onboarding.client_id != plan_data.client_id:
            raise ValueError(f"Onboarding não pertence ao cliente {plan_data.client_id}")
        
        # ✅ Validar se cliente já tem plano
        existing_plan = (
            db.query(Plan)
            .filter(Plan.client_id == plan_data.client_id)
            .first()
        )
        if existing_plan:
            raise ValueError(f"Cliente {plan_data.client_id} já possui um plano ativo")
        
        # ✅ Criar plano
        new_plan = Plan(
            client_id=plan_data.client_id,
            onboarding_id=plan_data.onboarding_id,
            training_plan=plan_data.training_plan,
            diet_plan=plan_data.diet_plan,
            notes=plan_data.notes,
        )
        
        # ✅ Apenas ADD (commit no router)
        db.add(new_plan)
        db.flush()  # Gera ID
        
        # ✅ Criar versão inicial (SEM commit, apenas flush)
        version_number = _get_next_version_number(db, plan_data.client_id)
        create_plan_version(
            db=db,
            client_id=plan_data.client_id,
            plan_id=new_plan.id,
            version_number=version_number,
            training_plan=new_plan.training_plan,
            diet_plan=new_plan.diet_plan,
            notes=new_plan.notes or "",
            change_reason="Plano criado manualmente",
        )
        
        return new_plan
        
    except IntegrityError as e:
        db.rollback()
        raise ValueError("Erro de integridade ao criar plano") from e
    except Exception as e:
        db.rollback()
        raise

def generate_automatic_plan(db: Session, client_id: int):
    """
    Gera um plano automático baseado no objetivo do cliente.
    
    Se já existe plano, retorna o existente (idempotente).
    """
    
    try:
        # ✅ Validar cliente
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError(f"Cliente com ID {client_id} não encontrado")
        
        # ✅ Buscar onboarding mais recente
        onboarding = (
            db.query(Onboarding)
            .filter(Onboarding.client_id == client_id)
            .order_by(Onboarding.id.desc())
            .first()
        )
        if not onboarding:
            raise ValueError(f"Nenhum onboarding encontrado para cliente {client_id}")
        
        # ✅ Se já existe plano, retorna (idempotente)
        existing_plan = db.query(Plan).filter(Plan.client_id == client_id).first()
        if existing_plan:
            return existing_plan
        
        # ✅ Gerar plano baseado no objetivo
        goal = (onboarding.main_goal or "").lower()
        
        if "emagrec" in goal:
            training_plan = "Treino A e B, 4x por semana, foco em gasto calórico, exercícios compostos e cardio moderado."
            diet_plan = "Dieta com 4 refeições, proteína alta, carboidrato controlado, déficit calórico leve."
            notes = "Priorizar constância, hidratação e progressão semanal."
        
        elif "hipertrof" in goal or "massa" in goal:
            training_plan = "Treino ABC, 5x por semana, foco em hipertrofia, progressão de carga e volume."
            diet_plan = "Dieta com 5 refeições, proteína alta, carboidratos mais altos, superávit calórico controlado."
            notes = "Priorizar recuperação, sono e aumento gradual de carga."
        
        else:
            training_plan = "Treino full body 3x por semana, foco em adaptação, técnica e regularidade."
            diet_plan = "Dieta equilibrada com 4 refeições, foco em organização e adesão."
            notes = "Ajustar plano conforme resposta nas próximas semanas."
        
        # ✅ Criar plano
        new_plan = Plan(
            client_id=client_id,
            onboarding_id=onboarding.id,
            training_plan=training_plan,
            diet_plan=diet_plan,
            notes=notes,
        )
        
        db.add(new_plan)
        db.flush()
        
        # ✅ Criar versão inicial
        version_number = _get_next_version_number(db, client_id)
        create_plan_version(
            db=db,
            client_id=client_id,
            plan_id=new_plan.id,
            version_number=version_number,
            training_plan=new_plan.training_plan,
            diet_plan=new_plan.diet_plan,
            notes=new_plan.notes or "",
            change_reason="Plano gerado automaticamente",
        )
        
        return new_plan
        
    except IntegrityError as e:
        db.rollback()
        raise ValueError("Erro de integridade ao gerar plano") from e
    except Exception as e:
        db.rollback()
        raise

def regenerate_plan(db: Session, client_id: int):
    """
    Regenera o plano de um cliente (deleta o antigo e cria novo).
    
    Mantém histórico via PlanVersion.
    """
    
    try:
        # ✅ Validar cliente
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError(f"Cliente com ID {client_id} não encontrado")
        
        # ✅ Buscar onboarding mais recente
        onboarding = (
            db.query(Onboarding)
            .filter(Onboarding.client_id == client_id)
            .order_by(Onboarding.id.desc())
            .first()
        )
        if not onboarding:
            raise ValueError(f"Nenhum onboarding encontrado para cliente {client_id}")
        
        # ✅ Deletar plano existente se houver
        existing_plan = db.query(Plan).filter(Plan.client_id == client_id).first()
        if existing_plan:
            db.delete(existing_plan)
            db.flush()
        
        # ✅ Gerar novo plano
        goal = (onboarding.main_goal or "").lower()
        
        if "emagrec" in goal:
            training_plan = "Treino A e B, 4x por semana, foco em gasto calórico, exercícios compostos e cardio moderado."
            diet_plan = "Dieta com 4 refeições, proteína alta, carboidrato controlado, déficit calórico leve."
            notes = "Plano regenerado. Priorizar constância, hidratação e progressão semanal."
        
        elif "hipertrof" in goal or "massa" in goal:
            training_plan = "Treino ABC, 5x por semana, foco em hipertrofia, progressão de carga e volume."
            diet_plan = "Dieta com 5 refeições, proteína alta, carboidratos mais altos, superávit calórico controlado."
            notes = "Plano regenerado. Priorizar recuperação, sono e aumento gradual de carga."
        
        else:
            training_plan = "Treino full body 3x por semana, foco em adaptação, técnica e regularidade."
            diet_plan = "Dieta equilibrada com 4 refeições, foco em organização e adesão."
            notes = "Plano regenerado. Ajustar conforme resposta nas próximas semanas."
        
        # ✅ Criar novo plano
        new_plan = Plan(
            client_id=client_id,
            onboarding_id=onboarding.id,
            training_plan=training_plan,
            diet_plan=diet_plan,
            notes=notes,
        )
        
        db.add(new_plan)
        db.flush()
        
        # ✅ Criar versão inicial
        version_number = _get_next_version_number(db, client_id)
        create_plan_version(
            db=db,
            client_id=client_id,
            plan_id=new_plan.id,
            version_number=version_number,
            training_plan=new_plan.training_plan,
            diet_plan=new_plan.diet_plan,
            notes=new_plan.notes or "",
            change_reason="Plano regenerado automaticamente",
        )
        
        return new_plan
        
    except IntegrityError as e:
        db.rollback()
        raise ValueError("Erro de integridade ao regenerar plano") from e
    except Exception as e:
        db.rollback()
        raise