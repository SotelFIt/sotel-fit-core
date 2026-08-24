"""
Conclusão de treino — endpoint canônico e idempotente (WORKOUT-DATA-001).

Contrato
--------
POST /workout-completions/{client_id}
    { idempotency_key, workout_key, completed_date? }
    -> 200 { created: bool, completion: {...} }

    A MESMA chave enviada N vezes produz:
      - uma única conclusão;
      - no máximo um evento de Timeline;
      - no máximo uma contribuição de marco;
      - sempre 200 com a conclusão existente. Nunca duplicação, nunca erro.

GET /workout-completions/{client_id}?since=YYYY-MM-DD
    -> lista das conclusões. É o que permite outro aparelho reconhecer o treino.

Transação
---------
Na primeira conclusão válida, a MESMA transação persiste a conclusão, cria o
evento de Timeline e calcula o marco. Falha em qualquer etapa → rollback total,
sem gravação parcial.

O marco é contado sobre `workout_completions`, NUNCA sobre `timeline_events`.
Era exatamente esse o risco do contrato antigo: reenviar inflava o contador.
"""
import json
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import require_client_access
from models.workout_completion import MARCOS, WorkoutCompletion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workout-completions", tags=["workout"])


class CompletionIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    workout_key: str = Field(min_length=1, max_length=32)
    completed_date: Optional[date] = None
    # Rótulos para a Timeline. Opcionais: o servidor tem fallback e NUNCA
    # depende do cliente para manter a integridade.
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)

    @field_validator("idempotency_key", "workout_key")
    @classmethod
    def _sem_espaco_vazio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("valor vazio")
        return v


def _serializar(c: WorkoutCompletion) -> dict:
    return {
        "id": c.id,
        "client_id": c.client_id,
        "client_plan_id": c.client_plan_id,
        "workout_key": c.workout_key,
        "completed_date": c.completed_date.isoformat() if c.completed_date else None,
        "completed_at": c.completed_at.isoformat() if c.completed_at else None,
        "idempotency_key": c.idempotency_key,
    }


def _plano_ativo_id(db: Session, client_id: int) -> int:
    """Plano publicado no momento da conclusão. 0 quando não há.

    Resolvido no SERVIDOR: é ele quem sabe o que está publicado, e assim o
    contrato de GET /clients/{id}/plan não precisa mudar.
    """
    try:
        row = db.execute(
            text(
                "SELECT id FROM client_plans WHERE client_id = :cid AND status = 'active' "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"cid": client_id},
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        # Base sem a tabela (ambiente de teste isolado) não pode derrubar a
        # conclusão: 0 = plano desconhecido, e a chave natural segue válida.
        db.rollback()
        return 0


def _inserir_evento(db: Session, client_id: int, event_type: str, title: str,
                    description: str, icon: str, meta: dict) -> Optional[int]:
    """INSERT do evento SEM commit — quem fecha a transação é o chamador.

    `create_event` de timeline.py não serve aqui: ele faz commit por conta
    própria, o que quebraria a atomicidade (conclusão gravada e evento não, ou
    o inverso).
    """
    sql = (
        "INSERT INTO timeline_events (client_id, event_type, title, description, icon, metadata, created_at) "
        "VALUES (:cid, :etype, :title, :desc, :icon, :meta, NOW())"
    )
    if db.bind.dialect.name != "postgresql":
        sql = sql.replace("NOW()", "CURRENT_TIMESTAMP")
    params = {
        "cid": client_id,
        "etype": event_type,
        "title": title,
        "desc": description,
        "icon": icon,
        "meta": json.dumps(meta),
    }
    try:
        res = db.execute(text(sql + " RETURNING id"), params)
        row = res.fetchone()
        return int(row[0]) if row else None
    except Exception:
        # RETURNING não suportado: o evento ainda precisa ser gravado, só não
        # recuperamos o id. A relação com a conclusão continua existindo pelo
        # `metadata`, que carrega a chave de idempotência.
        db.execute(text(sql), params)
        return None


def _existente(db: Session, client_id: int, dados: CompletionIn, dia: date):
    """Conclusão já registrada para esta intenção — por chave ou por ocorrência."""
    achado = (
        db.query(WorkoutCompletion)
        .filter(WorkoutCompletion.idempotency_key == dados.idempotency_key)
        .one_or_none()
    )
    if achado is None:
        achado = (
            db.query(WorkoutCompletion)
            .filter(
                WorkoutCompletion.client_id == client_id,
                WorkoutCompletion.workout_key == dados.workout_key,
                WorkoutCompletion.completed_date == dia,
            )
            .one_or_none()
        )
    return achado


@router.post("/{client_id}")
def concluir_treino(
    client_id: int,
    dados: CompletionIn,
    db: Session = Depends(get_db),
    _: int = Depends(require_client_access),
):
    dia = dados.completed_date or date.today()

    ja = _existente(db, client_id, dados, dia)
    if ja is not None:
        # Chave de OUTRO cliente: não confirmar e não vazar a existência dela.
        if ja.client_id != client_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
        return {"created": False, "completion": _serializar(ja)}

    plano_id = _plano_ativo_id(db, client_id)
    conclusao = WorkoutCompletion(
        client_id=client_id,
        client_plan_id=plano_id,
        workout_key=dados.workout_key,
        completed_date=dia,
        completed_at=datetime.utcnow(),
        idempotency_key=dados.idempotency_key,
    )

    try:
        db.add(conclusao)
        # flush (não commit): materializa o id e dispara a violação de unicidade
        # AGORA, antes de escrever qualquer evento de Timeline.
        db.flush()

        titulo = dados.title or f"Treino {dados.workout_key} concluído"
        meta = {
            "workout_completion_id": conclusao.id,
            "idempotency_key": conclusao.idempotency_key,
            "workout_key": conclusao.workout_key,
        }
        conclusao.timeline_event_id = _inserir_evento(
            db, client_id, "workout", titulo, dados.description or "", "🏆", meta
        )

        # MARCO: contado sobre as CONCLUSÕES, dentro da mesma transação. Como a
        # conclusão desta requisição já está no flush, ela entra na conta uma
        # única vez — reenviar não incrementa nada.
        total = (
            db.query(WorkoutCompletion)
            .filter(WorkoutCompletion.client_id == client_id)
            .count()
        )
        if total in MARCOS:
            icone, m_titulo, m_desc = MARCOS[total]
            _inserir_evento(
                db,
                client_id,
                "achievement",
                m_titulo,
                m_desc,
                icone,
                {"workout_completion_id": conclusao.id, "milestone": total},
            )

        db.commit()
    except IntegrityError:
        # Corrida: outra requisição gravou a mesma intenção entre a consulta e o
        # INSERT. Rollback desfaz TUDO (inclusive o evento) e devolvemos a
        # conclusão vencedora — sucesso, nunca erro.
        db.rollback()
        vencedora = _existente(db, client_id, dados, dia)
        if vencedora is None:
            logger.error("IntegrityError sem conclusão correspondente (client=%s)", client_id)
            raise HTTPException(status_code=500, detail="Erro ao registrar conclusão")
        if vencedora.client_id != client_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
        return {"created": False, "completion": _serializar(vencedora)}
    except Exception as e:
        db.rollback()
        logger.error("Erro ao registrar conclusão (client=%s): %s", client_id, e)
        raise HTTPException(status_code=500, detail="Erro ao registrar conclusão")

    db.refresh(conclusao)
    return {"created": True, "completion": _serializar(conclusao)}


@router.get("/{client_id}")
def listar_conclusoes(
    client_id: int,
    since: Optional[date] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: int = Depends(require_client_access),
):
    q = db.query(WorkoutCompletion).filter(WorkoutCompletion.client_id == client_id)
    if since is not None:
        q = q.filter(WorkoutCompletion.completed_date >= since)
    linhas = q.order_by(WorkoutCompletion.completed_date.desc(), WorkoutCompletion.id.desc()).limit(limit).all()
    return [_serializar(c) for c in linhas]
