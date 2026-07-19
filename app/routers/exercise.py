"""
LIB-003 - API da Biblioteca de Exercicios V1.

Endpoints minimos sobre a fundacao da LIB-002 (tabela `exercises` + trigger de
imutabilidade do slug). Escopo estrito:
  - Leitura autenticada:  GET /exercises  ·  GET /exercises/{slug}
  - CRUD administrativo:  POST /admin/exercises  ·  PATCH /admin/exercises/{slug}

Sem exclusao fisica (desativacao logica via is_active). Sem IA, sem planos texto,
sem telas admin, sem cadastro em massa. Nada de client tocado.

Convencao de auth reusada do backend:
  - `verify_dual_auth` -> qualquer autenticado (JWT de cliente OU API key admin).
  - admin = API key (verify_dual_auth -> 0) ou client_id conhecido de admin,
    mesma convencao dos demais /admin/* (routers/admin.py: ADMIN_CLIENT_IDS).
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import verify_dual_auth
from models.exercise import Exercise
from schemas.exercise import ExerciseCreate, ExerciseResponse, ExerciseUpdate

logger = logging.getLogger(__name__)

# Mesma convencao dos demais /admin/* deste backend (routers/admin.py).
ADMIN_CLIENT_IDS = {0, 2}


def require_admin(auth_client_id: int = Depends(verify_dual_auth)) -> int:
    if auth_client_id not in ADMIN_CLIENT_IDS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas admin")
    return auth_client_id


public_router = APIRouter(prefix="/exercises", tags=["exercises"])
admin_router = APIRouter(prefix="/admin/exercises", tags=["exercises-admin"])


# ---------------- helpers ----------------

def _active_substitution_slugs(db: Session, slugs) -> set:
    """Subconjunto de `slugs` que aponta para exercicios ATIVOS (para respostas publicas)."""
    slugs = [s for s in set(slugs or []) if s]
    if not slugs:
        return set()
    rows = (
        db.query(Exercise.slug)
        .filter(Exercise.slug.in_(slugs), Exercise.is_active.is_(True))
        .all()
    )
    return {r[0] for r in rows}


def _serialize(ex: Exercise, *, substitutions) -> dict:
    """Monta o dict de resposta com a lista de substituicoes ja resolvida."""
    data = ExerciseResponse.model_validate(ex).model_dump()
    data["approved_substitutions"] = list(substitutions)
    return data


def _public(ex: Exercise, active_slugs: set) -> dict:
    """Resposta publica: substituicoes filtradas para SOMENTE as ativas, preservando ordem."""
    subs = [s for s in (ex.approved_substitutions or []) if s in active_slugs]
    return _serialize(ex, substitutions=subs)


def _admin_view(ex: Exercise) -> dict:
    """Resposta administrativa: substituicoes como armazenadas (validadas na escrita)."""
    return _serialize(ex, substitutions=list(ex.approved_substitutions or []))


def _validate_substitutions(db: Session, own_slug: str, subs: Optional[List[str]]) -> None:
    """Regras de negocio das substituicoes aprovadas (usadas em create e update):
    - sem duplicacao;
    - sem autorreferencia (nao pode conter o proprio slug);
    - todos os slugs devem existir na biblioteca.
    """
    if subs is None:
        return
    if len(subs) != len(set(subs)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="approved_substitutions contem slugs duplicados",
        )
    if own_slug in subs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="approved_substitutions nao pode referenciar o proprio exercicio (autorreferencia)",
        )
    if subs:
        existing = {
            r[0] for r in db.query(Exercise.slug).filter(Exercise.slug.in_(subs)).all()
        }
        missing = [s for s in subs if s not in existing]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"approved_substitutions referencia exercicios inexistentes: {missing}",
            )


# ---------------- leitura autenticada ----------------

@public_router.get("", response_model=List[ExerciseResponse])
def list_exercises(
    primary_muscle: Optional[str] = Query(None),
    equipment: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    q: Optional[str] = Query(None, description="busca textual em name e slug"),
    db: Session = Depends(get_db),
    _auth: int = Depends(verify_dual_auth),
):
    query = db.query(Exercise)
    if primary_muscle:
        query = query.filter(func.lower(Exercise.primary_muscle) == primary_muscle.lower())
    if equipment:
        query = query.filter(func.lower(Exercise.equipment) == equipment.lower())
    if level:
        query = query.filter(Exercise.level == level)
    if is_active is not None:
        query = query.filter(Exercise.is_active.is_(is_active))
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            func.lower(Exercise.name).like(like) | func.lower(Exercise.slug).like(like)
        )
    items = query.order_by(Exercise.name).all()

    all_subs = {s for ex in items for s in (ex.approved_substitutions or [])}
    active = _active_substitution_slugs(db, all_subs)
    return [_public(ex, active) for ex in items]


@public_router.get("/{slug}", response_model=ExerciseResponse)
def get_exercise(
    slug: str,
    db: Session = Depends(get_db),
    _auth: int = Depends(verify_dual_auth),
):
    ex = db.query(Exercise).filter(Exercise.slug == slug).first()
    if not ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercicio nao encontrado")
    active = _active_substitution_slugs(db, set(ex.approved_substitutions or []))
    return _public(ex, active)


# ---------------- CRUD administrativo ----------------

@admin_router.post("", response_model=ExerciseResponse, status_code=status.HTTP_201_CREATED)
def create_exercise(
    payload: ExerciseCreate,
    db: Session = Depends(get_db),
    _admin: int = Depends(require_admin),
):
    if db.query(Exercise).filter(Exercise.slug == payload.slug).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"slug ja existe: {payload.slug}"
        )
    _validate_substitutions(db, payload.slug, payload.approved_substitutions)

    ex = Exercise(
        slug=payload.slug,
        name=payload.name,
        primary_muscle=payload.primary_muscle,
        secondary_muscles=list(payload.secondary_muscles),
        equipment=payload.equipment,
        level=payload.level,
        instructions=payload.instructions,
        common_errors=list(payload.common_errors),
        cautions=list(payload.cautions),
        approved_substitutions=list(payload.approved_substitutions),
        media=[m.model_dump() for m in payload.media],
        is_active=payload.is_active,
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    logger.info(f"Exercicio criado: slug={ex.slug}")
    return _admin_view(ex)


@admin_router.patch("/{slug}", response_model=ExerciseResponse)
def update_exercise(
    slug: str,
    payload: ExerciseUpdate,
    db: Session = Depends(get_db),
    _admin: int = Depends(require_admin),
):
    ex = db.query(Exercise).filter(Exercise.slug == slug).first()
    if not ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercicio nao encontrado")

    data = payload.model_dump(exclude_unset=True)

    # slug e imutavel: aceitar apenas se identico ao do path; qualquer mudanca -> 409.
    if "slug" in data:
        if data["slug"] != slug:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="slug e imutavel e nao pode ser alterado",
            )
        data.pop("slug")

    if "approved_substitutions" in data:
        _validate_substitutions(db, slug, data["approved_substitutions"])

    # media ja vem como list[dict] via model_dump; normaliza defensivamente.
    if "media" in data and data["media"] is not None:
        data["media"] = [
            m if isinstance(m, dict) else m.model_dump() for m in data["media"]
        ]

    for field, value in data.items():
        setattr(ex, field, value)

    db.commit()
    db.refresh(ex)
    logger.info(f"Exercicio atualizado: slug={ex.slug} campos={list(data.keys())}")
    return _admin_view(ex)
