from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from core.database import get_db
from core.security import verify_dual_auth
from schemas.checkin import CheckinCreate, CheckinResponse
from services.checkin_service import create_checkin, get_checkins_by_client, analyze_checkin, apply_checkin_decision
from services.subscription_service import can_access_client_content
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/checkins", tags=["checkins"])


def check_checkin_access(client_id: int, auth_client_id: int):
    if auth_client_id != 0 and auth_client_id != client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")


def check_subscription(client_id: int, auth_client_id: int, db):
    if auth_client_id != 0:
        if not can_access_client_content(db, client_id):
            raise HTTPException(status_code=403, detail="Seu plano esta vencido. Renove para continuar acessando.")


def _add_timeline_event(db: Session, client_id: int, checkin):
    try:
        treino = getattr(checkin, 'training_adherence', None) or '-'
        dieta = getattr(checkin, 'diet_adherence', None) or '-'
        energia = getattr(checkin, 'energy', None) or '-'
        peso = getattr(checkin, 'weight', None)

        desc_parts = [f"Treino: {treino} · Dieta: {dieta} · Energia: {energia}"]
        if peso:
            desc_parts.append(f"· Peso: {peso}kg")
        desc = " ".join(desc_parts)

        # Determina qualidade do check-in
        scores = []
        for val in [treino, dieta, energia]:
            try:
                scores.append(int(str(val).split('/')[0]))
            except Exception:
                pass

        avg = sum(scores) / len(scores) if scores else 3
        if avg >= 4.5:
            icon = "🔥"
            title = "Check-in excelente!"
        elif avg >= 3.5:
            icon = "💪"
            title = "Check-in muito bom!"
        elif avg >= 2.5:
            icon = "✅"
            title = "Check-in semanal concluido"
        else:
            icon = "📋"
            title = "Check-in registrado"

        db.execute(
            text("""
                INSERT INTO timeline_events (client_id, event_type, title, description, icon, created_at)
                VALUES (:cid, 'checkin', :title, :desc, :icon, NOW())
            """),
            {"cid": client_id, "desc": desc, "icon": icon, "title": title}
        )
    except Exception as e:
        logger.error(f"Erro ao criar evento de timeline: {e}")


def _add_ai_insight(db: Session, client_id: int, checkin):
    try:
        # Conta check-ins anteriores
        result = db.execute(
            text("SELECT COUNT(*) FROM client_checkins WHERE client_id = :cid"),
            {"cid": client_id}
        ).scalar()
        total_checkins = result or 0

        treino = getattr(checkin, 'training_adherence', None) or ''
        dieta = getattr(checkin, 'diet_adherence', None) or ''
        energia = getattr(checkin, 'energy', None) or ''
        peso = getattr(checkin, 'weight', None)

        scores = []
        for val in [treino, dieta, energia]:
            try:
                scores.append(int(str(val).split('/')[0]))
            except Exception:
                pass
        avg = sum(scores) / len(scores) if scores else 3

        insight_title = None
        insight_desc = None
        insight_icon = "⚡"

        if total_checkins == 1:
            insight_title = "Primeira semana registrada"
            insight_desc = "O sistema já está acompanhando sua evolução. Continue assim."
            insight_icon = "🚀"
        elif total_checkins % 4 == 0:
            insight_title = "Um mês de consistência"
            insight_desc = f"{total_checkins} check-ins concluídos. Consistência é o maior diferencial."
            insight_icon = "📈"
        elif avg >= 4.5:
            insight_title = "Semana acima da média"
            insight_desc = "Treino, dieta e energia no nível máximo. Ritmo de evolução acelerado."
            insight_icon = "🔥"
        elif avg <= 2:
            insight_title = "Semana desafiadora detectada"
            insight_desc = "Queda na aderência identificada. Seu personal será notificado para ajuste."
            insight_icon = "💤"
        elif total_checkins >= 3:
            insight_title = "Padrão de consistência identificado"
            insight_desc = "O sistema detectou presença contínua. Evolução sustentável em andamento."
            insight_icon = "🧠"

        if insight_title:
            db.execute(
                text("""
                    INSERT INTO timeline_events (client_id, event_type, title, description, icon, created_at)
                    VALUES (:cid, 'ai_insight', :title, :desc, :icon, NOW())
                """),
                {"cid": client_id, "desc": insight_desc, "icon": insight_icon, "title": insight_title}
            )
    except Exception as e:
        logger.error(f"Erro ao criar ai_insight: {e}")


@router.post("", response_model=CheckinResponse, status_code=status.HTTP_201_CREATED)
def create_new_checkin(checkin: CheckinCreate, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        if auth_client_id != 0 and auth_client_id != checkin.client_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
        check_subscription(checkin.client_id, auth_client_id, db)
        result = create_checkin(db, checkin)
        _add_timeline_event(db, checkin.client_id, result)
        _add_ai_insight(db, checkin.client_id, result)
        db.commit()
        db.refresh(result)
        return result
    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao criar check-in")


@router.get("/client/{client_id}", response_model=List[CheckinResponse])
def list_checkins(client_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        check_checkin_access(client_id, auth_client_id)
        check_subscription(client_id, auth_client_id, db)
        return get_checkins_by_client(db, client_id, skip, limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client/{client_id}/analysis")
def get_checkin_analysis(client_id: int, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        check_checkin_access(client_id, auth_client_id)
        check_subscription(client_id, auth_client_id, db)
        return analyze_checkin(db, client_id)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erro ao analisar check-in")


@router.post("/client/{client_id}/apply-decision")
def apply_decision(client_id: int, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    try:
        check_checkin_access(client_id, auth_client_id)
        result = apply_checkin_decision(db, client_id)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao aplicar decisao")