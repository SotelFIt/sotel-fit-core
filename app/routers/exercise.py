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
  - admin -> mecanismo OFICIAL `core.security.require_admin` (API key -> 0).
    (BLOCKER 1 da auditoria: removido o bypass local {0,2}; sem politica nova.)
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from core.database import get_db
from core.security import require_admin, verify_dual_auth
from models.exercise import Exercise
from models.exercise_substitution import ExerciseSubstitutionRule
from schemas.exercise import ExerciseCreate, ExerciseResponse, ExerciseUpdate
from services.exercise_resolver import resolve_exercise
from services.substitution_rules import (
    get_substitution_decision,
    projected_substitutions,
    projected_substitutions_bulk,
)

logger = logging.getLogger(__name__)

# Admin desta API == autenticacao administrativa oficial (verify_dual_auth -> 0).
ADMIN_AUTH_ID = 0


public_router = APIRouter(prefix="/exercises", tags=["exercises"])
admin_router = APIRouter(prefix="/admin/exercises", tags=["exercises-admin"])


# ---------------- helpers ----------------

def _active_substitution_slugs(db: Session, slugs) -> set:
    """Legado da LIB-003; a filtragem por alvo ativo passou para a projecao (LIB-013B)."""
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


def _public(ex: Exercise, projecao: dict) -> dict:
    """Resposta publica: projecao (direct+acceptable) com alvos ATIVOS."""
    return _serialize(ex, substitutions=projecao.get(ex.id, []))


def _admin_view(db: Session, ex: Exercise) -> dict:
    """Resposta administrativa: mesma projecao, incluindo alvos inativos.

    LIB-013B: `approved_substitutions` deixou de ser fonte da verdade e virou
    PROJECAO de exercise_substitution_rules (direct + acceptable). A coluna JSON
    antiga continua no banco por compatibilidade, mas nao e lida nem escrita -
    manter duas fontes seria admitir divergencia silenciosa.
    """
    return _serialize(ex, substitutions=projected_substitutions(db, ex.id, somente_alvo_ativo=False))


def _recusar_escrita_de_substituicoes(subs: Optional[List[str]]) -> None:
    """LIB-013B: `approved_substitutions` e somente leitura (projecao).

    Aceitar escrita aqui recriaria o dual-write que a missao proibe: o JSON e a
    tabela de regras poderiam divergir sem ninguem perceber. Escrever uma lista
    vazia continua permitido para nao quebrar clientes que reenviam o payload
    inteiro - ela ja e o valor projetado quando nao ha regra.
    """
    if subs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=("approved_substitutions e derivado de exercise_substitution_rules e nao pode "
                    "ser escrito diretamente (LIB-013B). Registre a relacao como regra direcional."),
        )


def _validate_substitutions_legado(db: Session, own_slug: str, subs: Optional[List[str]]) -> None:
    """Mantido para referencia historica; nao e mais chamado nos endpoints."""
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
    auth_id: int = Depends(verify_dual_auth),
):
    is_admin = auth_id == ADMIN_AUTH_ID
    query = db.query(Exercise)
    if primary_muscle:
        query = query.filter(func.lower(Exercise.primary_muscle) == primary_muscle.lower())
    if equipment:
        query = query.filter(func.lower(Exercise.equipment) == equipment.lower())
    if level:
        query = query.filter(Exercise.level == level)
    # BLOCKER 5: cliente comum enxerga SOMENTE ativos (o filtro is_active dele e
    # ignorado); inativos so aparecem para autenticacao administrativa.
    if is_admin:
        if is_active is not None:
            query = query.filter(Exercise.is_active.is_(is_active))
    else:
        query = query.filter(Exercise.is_active.is_(True))
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            func.lower(Exercise.name).like(like) | func.lower(Exercise.slug).like(like)
        )
    items = query.order_by(Exercise.name).all()

    projecao = projected_substitutions_bulk(db, [ex.id for ex in items])
    return [_public(ex, projecao) for ex in items]


@public_router.get("/resolve")
def resolve_exercise_name(
    name: str = Query(..., min_length=1, description="nome livre a resolver contra name+aliases"),
    db: Session = Depends(get_db),
    _auth: int = Depends(verify_dual_auth),
):
    """Estrutura OFICIAL de resolucao da Biblioteca (consumida pela LIB-005).
    Casa a forma normalizada de `name` contra name + aliases dos exercicios ativos.
    200 {slug, match:'canonical'|'alias'}  ·  404 se nao houver identidade canonica.
    Declarada ANTES de /{slug} para nao ser capturada como slug='resolve'.
    """
    hit = resolve_exercise(db, name)
    if not hit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sem identidade canonica")
    return hit


@public_router.get("/{slug}", response_model=ExerciseResponse)
def get_exercise(
    slug: str,
    db: Session = Depends(get_db),
    auth_id: int = Depends(verify_dual_auth),
):
    is_admin = auth_id == ADMIN_AUTH_ID
    ex = db.query(Exercise).filter(Exercise.slug == slug).first()
    # BLOCKER 5: inativo e invisivel para cliente comum (404, como se nao existisse).
    if not ex or (not is_admin and not ex.is_active):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercicio nao encontrado")
    return _public(ex, {ex.id: projected_substitutions(db, ex.id)})


@public_router.get("/{slug}/substitutions/{target_slug}")
def substitution_decision(
    slug: str,
    target_slug: str,
    db: Session = Depends(get_db),
    _auth: int = Depends(verify_dual_auth),
):
    """LIB-013B - unica porta de decisao sobre substituicao.

    Responde para o par ORIENTADO {slug} -> {target_slug}:
      YES | NO | DEPENDS | NOT_EVALUATED

    A aresta inversa NUNCA e consultada como fallback. Se o par nunca foi
    avaliado nesta direcao a resposta e NOT_EVALUATED - que nao e "nao pode".
    """
    return get_substitution_decision(db, slug, target_slug)


@admin_router.get("/substitution-rules")
def list_substitution_rules(
    db: Session = Depends(get_db),
    _admin: int = Depends(require_admin),
):
    """Listagem administrativa das regras (auditoria e importer). Somente leitura."""
    origem = aliased(Exercise)
    alvo = aliased(Exercise)
    linhas = (
        db.query(origem.slug, alvo.slug, ExerciseSubstitutionRule)
        .join(origem, ExerciseSubstitutionRule.source_exercise_id == origem.id)
        .join(alvo, ExerciseSubstitutionRule.target_exercise_id == alvo.id)
        .order_by(origem.slug, alvo.slug)
        .all()
    )
    return [
        {"source": s, "target": t, "relation_type": r.relation_type, "rationale": r.rationale,
         "condition": r.condition, "is_active": r.is_active}
        for s, t, r in linhas
    ]


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
    _recusar_escrita_de_substituicoes(payload.approved_substitutions)

    ex = Exercise(
        slug=payload.slug,
        name=payload.name,
        aliases=list(payload.aliases),
        primary_muscle=payload.primary_muscle,
        secondary_muscles=list(payload.secondary_muscles),
        equipment=payload.equipment,
        level=payload.level,
        instructions=payload.instructions,
        common_errors=list(payload.common_errors),
        cautions=list(payload.cautions),
        approved_substitutions=[],  # LIB-013B: coluna legada nasce vazia; a verdade vive nas regras
        media=[m.model_dump() for m in payload.media],
        is_active=payload.is_active,
    )
    db.add(ex)
    # BLOCKER 4: o SELECT previo e apenas otimizacao; a autoridade da unicidade e
    # a constraint no commit. Captura a violacao, faz rollback e responde 409
    # (cobre a corrida em que dois inserts passam pelo SELECT antes do commit).
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"slug ja existe: {payload.slug}"
        )
    db.refresh(ex)
    logger.info(f"Exercicio criado: slug={ex.slug}")
    return _admin_view(db, ex)


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
        _recusar_escrita_de_substituicoes(data["approved_substitutions"])
        data.pop("approved_substitutions")  # projecao: nunca persistida a partir do payload

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
    return _admin_view(db, ex)
