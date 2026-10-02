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
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import require_admin, verify_dual_auth
from models.exercise import Exercise
from schemas.exercise import ExerciseCreate, ExerciseResponse, ExerciseUpdate
from services.exercise_resolver import resolve_exercise

logger = logging.getLogger(__name__)

# Admin desta API == autenticacao administrativa oficial (verify_dual_auth -> 0).
ADMIN_AUTH_ID = 0


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

    all_subs = {s for ex in items for s in (ex.approved_substitutions or [])}
    active = _active_substitution_slugs(db, all_subs)
    return [_public(ex, active) for ex in items]


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
        aliases=list(payload.aliases),
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


# ===========================================================================
# YMOVE - demonstracao em video de fornecedor externo.
#
# Divisao de responsabilidade que vale para todas as rotas abaixo:
#
#   ADMIN  navega o catalogo do fornecedor (browse mode, sem consumir cota),
#          confere e salva o vinculo. Ve o consumo real da conta.
#   ALUNO  pede a demonstracao de um exercicio que esta no SEU treino
#          publicado - e so nesse momento uma URL assinada e gerada.
#
# A chave do fornecedor nunca sai do servidor. Nenhuma destas rotas aceita URL
# ou id arbitrario para repassar: o aluno pede pelo SLUG do exercicio DELE, e o
# id do fornecedor sai do vinculo que um humano aprovou.
# ===========================================================================

from datetime import datetime, timezone

from schemas.exercise import ExternalDemo
from services import ymove


def _erro_do_fornecedor(e: Exception) -> HTTPException:
    """Traduz a falha do fornecedor para algo que a tela possa dizer.

    Nenhuma mensagem do fornecedor passa crua: ela pode conter detalhe de
    conta, de plano ou da propria chamada.
    """
    if isinstance(e, ymove.YMoveSemCredencial):
        return HTTPException(status_code=503, detail="integracao de video nao configurada")
    if isinstance(e, ymove.YMoveLimiteAtingido):
        return HTTPException(status_code=429, detail="limite do fornecedor de video atingido")
    if isinstance(e, ymove.YMoveNaoEncontrado):
        return HTTPException(status_code=404, detail="demonstracao nao encontrada no fornecedor")
    return HTTPException(status_code=503, detail="fornecedor de video indisponivel")


@admin_router.get("/ymove/buscar")
def buscar_no_ymove(
    q: Optional[str] = Query(None, description="texto livre; o nome em portugues serve de ponto de partida"),
    muscle_group: Optional[str] = Query(None),
    equipment: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    _admin: int = Depends(require_admin),
):
    """Candidatos para o vinculo. **Nao consome cota**: browse mode.

    Semelhanca de nome SUGERE; nao decide. Por isso a resposta traz
    equipamento, grupo muscular e variantes - sem eles nao da para distinguir
    execucoes parecidas, e vincular errado ensina o movimento errado.
    """
    if not ymove.configurado():
        raise HTTPException(status_code=503, detail="integracao de video nao configurada")
    try:
        return ymove.buscar(termo=q, muscle_group=muscle_group, equipment=equipment, page=page)
    except Exception as e:
        raise _erro_do_fornecedor(e)


@admin_router.get("/ymove/uso")
def uso_do_ymove(_admin: int = Depends(require_admin)):
    """Consumo real da conta no fornecedor. So admin - nunca na tela do aluno.

    A unidade de cobranca e EXERCICIO DISTINTO em 30 dias
    (`monthlyExercisesUsed`), nao segundo assistido: repetir o mesmo exercicio
    no mesmo mes nao soma de novo; abrir um exercicio novo soma.
    """
    if not ymove.configurado():
        raise HTTPException(status_code=503, detail="integracao de video nao configurada")
    try:
        return ymove.uso()
    except Exception as e:
        raise _erro_do_fornecedor(e)


@admin_router.put("/{slug}/ymove")
def vincular_ymove(
    slug: str,
    payload: dict,
    db: Session = Depends(get_db),
    _admin: int = Depends(require_admin),
):
    """Salva o vinculo aprovado por um humano.

    O slug LOCAL nao muda: continua sendo a identidade da prescricao. O que
    entra e um ponteiro para o catalogo do fornecedor.
    """
    ex = db.query(Exercise).filter(Exercise.slug == slug).first()
    if not ex:
        raise HTTPException(status_code=404, detail=f"exercicio nao encontrado: {slug}")

    dados = dict(payload or {})
    dados.setdefault("provider", "ymove")
    dados["linked_at"] = datetime.now(timezone.utc).isoformat()
    try:
        demo = ExternalDemo(**dados)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"vinculo invalido: {e}")

    ex.external_demo = demo.model_dump(mode="json", exclude_none=True)
    db.commit()
    db.refresh(ex)
    logger.info("vinculo YMove salvo slug=%s provider_id=%s", slug, demo.exercise_id)
    return {"slug": slug, "external_demo": ex.external_demo}


@admin_router.delete("/{slug}/ymove")
def desvincular_ymove(
    slug: str,
    db: Session = Depends(get_db),
    _admin: int = Depends(require_admin),
):
    """Remove o vinculo. Nao toca na prescricao nem na midia propria."""
    ex = db.query(Exercise).filter(Exercise.slug == slug).first()
    if not ex:
        raise HTTPException(status_code=404, detail=f"exercicio nao encontrado: {slug}")
    ex.external_demo = None
    db.commit()
    return {"slug": slug, "external_demo": None}


@admin_router.get("/ymove/cobertura")
def cobertura_das_prescricoes(
    db: Session = Depends(get_db),
    _admin: int = Depends(require_admin),
):
    """Cobertura das ocorrencias REALMENTE usadas nas prescricoes ativas.

    Nao e a cobertura do catalogo inteiro: varrer a Biblioteca toda infla o
    numero com exercicios que ninguem prescreve. Aqui conta o que esta nos
    planos ativos, com quantas vezes aparece - a fila de revisao sai ordenada
    por impacto real.
    """
    import json as _json

    try:
        linhas = db.execute(
            text("SELECT enrichment_json FROM client_plans "
                 "WHERE status = 'active' AND enrichment_json IS NOT NULL")
        ).fetchall()
    except Exception:
        db.rollback()
        linhas = []

    ocorrencias = {}
    nao_resolvidas = {}
    for (bruto,) in linhas:
        try:
            enr = _json.loads(bruto) if isinstance(bruto, str) else (bruto or {})
        except Exception:
            continue
        for oc in (enr.get("exercises") or []):
            ref = (oc or {}).get("library_ref")
            if ref:
                ocorrencias[ref] = ocorrencias.get(ref, 0) + 1
            elif (oc or {}).get("status") != "ruido_estrutural":
                nome = ((oc or {}).get("name_raw") or "").strip()
                if nome:
                    nao_resolvidas[nome] = nao_resolvidas.get(nome, 0) + 1

    vinculados = {
        r[0] for r in db.query(Exercise.slug)
        .filter(Exercise.external_demo.isnot(None)).all()
    }
    com, sem = [], []
    for slug, n in sorted(ocorrencias.items(), key=lambda x: -x[1]):
        (com if slug in vinculados else sem).append({"slug": slug, "ocorrencias": n})

    return {
        "ocorrencias_totais": sum(ocorrencias.values()),
        "ocorrencias_com_demonstracao": sum(i["ocorrencias"] for i in com),
        "exercicios_distintos": len(ocorrencias),
        "com_demonstracao": com,
        # Fila de revisao: o que o aluno encontra e ainda nao tem demonstracao.
        "fila_de_revisao": sem,
        # Nomes do plano que nem chegam a um exercicio da Biblioteca. Nao sao
        # candidatos a vinculo - sao lacuna de catalogo, outra fila.
        "sem_correspondencia_na_biblioteca": [
            {"nome": k, "ocorrencias": v}
            for k, v in sorted(nao_resolvidas.items(), key=lambda x: -x[1])
        ],
    }


def _cliente_esta_excluido(db: Session, client_id: int) -> bool:
    """Cadastro excluido nao consome o fornecedor.

    Falha de banco responde "excluido" DE PROPOSITO: liberar acesso porque a
    consulta caiu seria transformar indisponibilidade em permissao.
    """
    try:
        linha = db.execute(
            text("SELECT deleted_at FROM clients WHERE id = :cid"), {"cid": client_id}
        ).fetchone()
    except Exception:
        db.rollback()
        return True
    if linha is None:
        return True
    return linha[0] is not None


def _slug_no_plano_do_cliente(db: Session, client_id: int, slug: str) -> bool:
    """O exercicio esta no treino publicado deste aluno?

    Le o enriquecimento do plano ativo, onde cada ocorrencia da prescricao ja
    guarda o `library_ref` resolvido. Sem plano ou sem enriquecimento a
    resposta e NAO: ausencia de prova nao e permissao.
    """
    import json as _json

    try:
        linha = db.execute(
            text("SELECT enrichment_json FROM client_plans WHERE client_id = :cid "
                 "AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
            {"cid": client_id},
        ).fetchone()
    except Exception:
        db.rollback()
        return False
    if not linha or not linha[0]:
        return False
    try:
        enr = _json.loads(linha[0]) if isinstance(linha[0], str) else linha[0]
    except Exception:
        return False
    return any(
        (oc or {}).get("library_ref") == slug for oc in (enr.get("exercises") or [])
    )


@public_router.get("/{slug}/demo")
def demonstracao_do_exercicio(
    slug: str,
    db: Session = Depends(get_db),
    auth_id: int = Depends(verify_dual_auth),
):
    """URL assinada da demonstracao. **So aqui** o video e pedido ao fornecedor.

    Autorizacao em tres camadas, porque cada uma cobre um buraco diferente:

      1. autenticado (herdado de `verify_dual_auth`);
      2. aluno EXCLUIDO nao passa - quem manda e o cadastro, nao o token, que
         continua com assinatura valida;
      3. o exercicio precisa estar no treino publicado DO SOLICITANTE. Sem
         isso, qualquer aluno autenticado viraria um proxy para o catalogo
         inteiro do fornecedor, gastando cota por conta propria.

    A URL nao e gravada em lugar nenhum: expira em 48h e e pedida de novo na
    proxima vez.
    """
    ex = db.query(Exercise).filter(
        Exercise.slug == slug, Exercise.is_active.is_(True)
    ).first()
    if not ex or not ex.external_demo:
        raise HTTPException(status_code=404, detail="sem demonstracao para este exercicio")

    if auth_id != ADMIN_AUTH_ID:
        if _cliente_esta_excluido(db, auth_id):
            raise HTTPException(status_code=401, detail="Cadastro inativo")
        if not _slug_no_plano_do_cliente(db, auth_id, slug):
            raise HTTPException(status_code=403, detail="exercicio fora do seu treino")

    demo = ex.external_demo or {}
    try:
        video = ymove.url_de_video(
            demo.get("exercise_id") or demo.get("slug"), demo.get("variant")
        )
    except Exception as e:
        raise _erro_do_fornecedor(e)

    return {
        "slug": slug,
        "url": video["url"],
        "orientacao": video.get("orientacao"),
        "duracao_s": video.get("duracao_s"),
        "thumbnail": demo.get("thumbnail_url") or video.get("thumbnail"),
        # Dito explicitamente para o cliente nao cachear: a URL morre em 48h.
        "expira_em_horas": 48,
    }
