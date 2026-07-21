"""
exercise_resolver - Resolucao de nome -> identidade canonica da Biblioteca.

DOMINIO: Biblioteca de Exercicios (LIB-003+). Aqui vive TODO o conhecimento de
correspondencia: a normalizacao generica e o casamento contra `name` + `aliases[]`.
A LIB-005 (binding) NAO conhece sinonimos: ela apenas chama estas funcoes.

Regras (contrato congelado):
- correspondencia SOMENTE deterministica: igualdade da forma normalizada;
- nome canonico tem precedencia sobre alias;
- sem similaridade probabilistica, sem "chute";
- somente exercicios ATIVOS participam da resolucao.
"""
import re
import unicodedata
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from models.exercise import Exercise

_PARENS = re.compile(r"\([^)]*\)")
_NONALNUM = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")


def normalize_name(s: str) -> str:
    """Forma canonica GENERICA (sem conhecimento de sinonimo):
    minuscula, sem acento, sem conteudo entre parenteses, sem pontuacao,
    espacos colapsados. Ex.: '- Leg Press (pés altos)' -> 'leg press'.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # remove acentos
    s = s.lower()
    s = _PARENS.sub(" ", s)      # remove qualificadores entre parenteses
    s = _NONALNUM.sub(" ", s)    # tudo que nao e [a-z0-9] vira espaco
    s = _WS.sub(" ", s).strip()
    return s


def build_index(db: Session) -> Dict[str, Tuple[str, str]]:
    """Indice {forma_normalizada: (slug, match)} sobre exercicios ATIVOS.
    `match` in {'canonical','alias'}. Canonico nunca e sobrescrito por alias;
    empates resolvem-se de forma estavel (ordem por slug)."""
    index: Dict[str, Tuple[str, str]] = {}
    rows = (
        db.query(Exercise)
        .filter(Exercise.is_active.is_(True))
        .order_by(Exercise.slug)
        .all()
    )
    # 1a passada: nomes canonicos (precedencia)
    for ex in rows:
        key = normalize_name(ex.name)
        if key and key not in index:
            index[key] = (ex.slug, "canonical")
    # 2a passada: aliases (nao sobrescrevem canonico)
    for ex in rows:
        for alias in (getattr(ex, "aliases", None) or []):
            key = normalize_name(alias)
            if key and key not in index:
                index[key] = (ex.slug, "alias")
    return index


def resolve_with_index(index: Dict[str, Tuple[str, str]], name: str) -> Optional[dict]:
    hit = index.get(normalize_name(name))
    if not hit:
        return None
    return {"slug": hit[0], "match": hit[1]}


def resolve_exercise(db: Session, name: str) -> Optional[dict]:
    """Resolucao de um unico nome (usada pelo endpoint oficial)."""
    return resolve_with_index(build_index(db), name)
