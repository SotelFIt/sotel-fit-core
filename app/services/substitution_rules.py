"""
substitution_rules - unica porta de decisao sobre substituicao (LIB-013B).

Quem quiser saber se X pode virar Y pergunta AQUI. Nao ha segunda implementacao,
e nao ha atalho lendo a tabela direto: a regra de direcao mora nesta funcao.

Regra que da nome a missao: a consulta e SEMPRE source -> target. A aresta
inversa NAO e usada como fallback. Foi assim que uma leitura ingenua do modelo
antigo respondeu "pode substituir leg press por agachamento livre" citando a
aresta que existia no sentido contrario.
"""
from typing import Optional

from sqlalchemy.orm import Session

from models.exercise import Exercise
from models.exercise_substitution import ExerciseSubstitutionRule

# relation_type -> decisao exposta ao consumidor
DECISION_BY_RELATION = {
    "direct": "YES",
    "acceptable": "YES",
    "contextual": "DEPENDS",
    "rejected": "NO",
}
NOT_EVALUATED = "NOT_EVALUATED"

# o que alimenta a projecao legada `approved_substitutions`
POSITIVE_RELATIONS = ("direct", "acceptable")


def get_substitution_decision(db: Session, source_slug: str, target_slug: str) -> dict:
    """Decisao para o par ORIENTADO source -> target.

    Retorna sempre um dict com:
      decision: YES | NO | DEPENDS | NOT_EVALUATED
      relation_type, rationale, condition: preenchidos so quando ha regra.

    Ausencia de regra e NOT_EVALUATED - nunca NO. Sao coisas diferentes:
    "ninguem avaliou" nao autoriza afirmar "nao pode".
    """
    src = db.query(Exercise).filter(Exercise.slug == source_slug).first()
    tgt = db.query(Exercise).filter(Exercise.slug == target_slug).first()
    if src is None or tgt is None:
        return {"decision": NOT_EVALUATED, "relation_type": None, "rationale": None,
                "condition": None, "reason": "exercicio inexistente na Biblioteca"}

    rule = (
        db.query(ExerciseSubstitutionRule)
        .filter(
            ExerciseSubstitutionRule.source_exercise_id == src.id,
            ExerciseSubstitutionRule.target_exercise_id == tgt.id,
            ExerciseSubstitutionRule.is_active.is_(True),
        )
        .first()
    )
    if rule is None:
        return {"decision": NOT_EVALUATED, "relation_type": None, "rationale": None,
                "condition": None, "reason": "par ainda nao avaliado nesta direcao"}

    return {
        "decision": DECISION_BY_RELATION[rule.relation_type],
        "relation_type": rule.relation_type,
        "rationale": rule.rationale,
        "condition": rule.condition,
        "reason": None,
    }


def projected_substitutions(db: Session, source_id: int, *, somente_alvo_ativo: bool = True) -> list:
    """PROJECAO do campo legado `approved_substitutions`.

    Deriva de direct + acceptable, nesta direcao. O campo JSON antigo nao e mais
    lido nem escrito: existe uma unica fonte da verdade, e e esta tabela.
    """
    q = (
        db.query(Exercise.slug, ExerciseSubstitutionRule.relation_type)
        .join(ExerciseSubstitutionRule,
              ExerciseSubstitutionRule.target_exercise_id == Exercise.id)
        .filter(
            ExerciseSubstitutionRule.source_exercise_id == source_id,
            ExerciseSubstitutionRule.is_active.is_(True),
            ExerciseSubstitutionRule.relation_type.in_(POSITIVE_RELATIONS),
        )
    )
    if somente_alvo_ativo:
        q = q.filter(Exercise.is_active.is_(True))
    # ordem estavel: 'direct' antes de 'acceptable', depois alfabetica
    linhas = sorted(q.all(), key=lambda r: (POSITIVE_RELATIONS.index(r[1]), r[0]))
    return [slug for slug, _ in linhas]


def projected_substitutions_bulk(db: Session, source_ids, *, somente_alvo_ativo: bool = True) -> dict:
    """Mesma projecao para varios exercicios em UMA consulta (usado na listagem)."""
    ids = list(source_ids or [])
    if not ids:
        return {}
    q = (
        db.query(ExerciseSubstitutionRule.source_exercise_id, Exercise.slug,
                 ExerciseSubstitutionRule.relation_type)
        .join(ExerciseSubstitutionRule,
              ExerciseSubstitutionRule.target_exercise_id == Exercise.id)
        .filter(
            ExerciseSubstitutionRule.source_exercise_id.in_(ids),
            ExerciseSubstitutionRule.is_active.is_(True),
            ExerciseSubstitutionRule.relation_type.in_(POSITIVE_RELATIONS),
        )
    )
    if somente_alvo_ativo:
        q = q.filter(Exercise.is_active.is_(True))
    out: dict = {}
    for source_id, slug, rel in q.all():
        out.setdefault(source_id, []).append((POSITIVE_RELATIONS.index(rel), slug))
    return {k: [s for _, s in sorted(v)] for k, v in out.items()}


def validate_rule(relation_type: str, rationale: Optional[str], condition: Optional[str]) -> Optional[str]:
    """Regras de conteudo, independentes de banco. Retorna a mensagem de erro ou None."""
    if relation_type not in DECISION_BY_RELATION:
        return f"relation_type invalido: {relation_type!r}"
    if not (rationale or "").strip():
        return "rationale e obrigatorio: relacao sem racional nao e auditavel"
    if relation_type == "contextual" and not (condition or "").strip():
        return "relation_type 'contextual' exige `condition`: sem contexto a resposta DEPENDS e inutil"
    return None
