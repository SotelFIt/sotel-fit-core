from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.checkin import Checkin
from models.client import Client
from services.plan_service import regenerate_plan
from services.decision_log_service import create_decision_log

def create_checkin(db: Session, data):
    try:
        client = db.query(Client).filter(Client.id == data.client_id).first()
        if not client:
            raise ValueError(f"Cliente {data.client_id} nao encontrado")
        
        new_checkin = Checkin(
            client_id=data.client_id,
            week_label=data.week_label,
            weight=data.weight,
            diet_adherence=data.diet_adherence,
            training_adherence=data.training_adherence,
            energy=data.energy,
            difficulties=data.difficulties,
            notes=data.notes,
        )
        
        db.add(new_checkin)
        db.flush()
        return new_checkin
    except IntegrityError:
        db.rollback()
        raise ValueError("Erro integridade")
    except Exception:
        db.rollback()
        raise

def get_checkins_by_client(db: Session, client_id: int):
    return db.query(Checkin).filter(Checkin.client_id == client_id).all()

def get_latest_checkin_by_client(db: Session, client_id: int):
    return db.query(Checkin).filter(Checkin.client_id == client_id).order_by(Checkin.id.desc()).first()

def analyze_checkin(db: Session, client_id: int):
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError(f"Cliente {client_id} nao encontrado")
        
        checkin = get_latest_checkin_by_client(db, client_id)
        if not checkin:
            raise ValueError(f"Nenhum checkin para cliente {client_id}")
        
        alerts = []
        status = "manter plano"
        
        diet = (checkin.diet_adherence or "").lower()
        training = (checkin.training_adherence or "").lower()
        energy = (checkin.energy or "").lower()
        difficulties = (checkin.difficulties or "").lower()
        
        if any(x in diet for x in ["60", "50", "40", "30"]):
            alerts.append("Baixa adesao")
            status = "ajustar dieta"
        
        if any(x in training for x in ["60", "50", "40", "30"]):
            alerts.append("Treino baixo")
            status = "regenerar plano"
        
        if any(x in energy for x in ["ruim", "baixa"]):
            alerts.append("Energia baixa")
            if status == "manter plano":
                status = "ajustar plano"
        
        if "fome" in difficulties:
            alerts.append("Fome")
            if status == "manter plano":
                status = "ajustar dieta"
        
        if "dor" in difficulties or "lesao" in difficulties:
            alerts.append("Dor ou lesao")
            status = "regenerar plano"
        
        if not alerts:
            alerts.append("Tudo bem")
        
        summary = f"Peso: {checkin.weight} kg"
        
        return {
            "checkin_id": checkin.id,
            "client_id": client_id,
            "status": status,
            "alerts": alerts,
            "summary": summary
        }
    except Exception:
        raise

def apply_checkin_decision(db: Session, client_id: int):
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError(f"Cliente {client_id} nao encontrado")
        
        analysis = analyze_checkin(db, client_id)
        status = analysis["status"]
        
        if status == "manter plano":
            decision = "Mantido"
        elif status == "ajustar dieta":
            decision = "Ajustar dieta"
        elif status == "ajustar plano":
            decision = "Ajustar plano"
        elif status == "regenerar plano":
            regenerate_plan(db, client_id)
            decision = "Regenerado"
        else:
            decision = "Nenhuma acao"
        
        return {
            "client_id": client_id,
            "decision": decision,
            "status": status,
            "alerts": analysis["alerts"],
            "summary": analysis["summary"]
        }
    except Exception:
        raise
