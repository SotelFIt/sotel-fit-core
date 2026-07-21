"""
exercise_binding - Vinculo prescricao -> exercicio (LIB-005, Parte B).

Consumidor puro: extrai as ocorrencias do texto (workout_extract) e resolve cada
uma contra a estrutura OFICIAL da Biblioteca (exercise_resolver). NAO mantem lista
de aliases; NAO altera published_content; produz um artefato DERIVADO e ADITIVO.

Determinismo/idempotencia: para um mesmo `published_content`, a saida e identica
(funcao pura sobre o texto + estado da Biblioteca). `source_hash` permite pular
recomputo e detectar defasagem.
"""
import hashlib
from typing import Optional

from sqlalchemy.orm import Session

from services.workout_extract import extract_exercises
from services.exercise_resolver import build_index, resolve_with_index, normalize_name


def compute_source_hash(published_content: Optional[str]) -> str:
    return hashlib.sha256((published_content or "").encode("utf-8")).hexdigest()


def _occurrence_key(norm: str, ordinal: int, context_path: str) -> str:
    """Identidade estavel POR SNAPSHOT (funcao pura do conteudo, nao posicional):
    forma normalizada + ordinal da ocorrencia desse nome nesse contexto + contexto."""
    raw = f"{norm}#{ordinal}@{context_path}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def build_enrichment(db: Session, published_content: Optional[str]) -> dict:
    """Enriquecimento derivado do texto publicado:
    { "exercises": [ {occurrence_key, name_raw, context_path, library_ref, status, match?} ],
      "coverage": {resolved, total} }.
    """
    items = extract_exercises(published_content or "")
    index = build_index(db)

    exercises = []
    seen = {}
    resolved = 0
    for it in items:
        norm = normalize_name(it["name"])
        ctx = it["context_path"]
        ordinal = seen.get((norm, ctx), 0)
        seen[(norm, ctx)] = ordinal + 1

        hit = resolve_with_index(index, it["name"])
        entry = {
            "occurrence_key": _occurrence_key(norm, ordinal, ctx),
            "name_raw": it["name"],
            "context_path": ctx,
            "library_ref": hit["slug"] if hit else None,
            "status": "resolved" if hit else "unresolved",
        }
        if hit:
            entry["match"] = hit["match"]
            resolved += 1
        exercises.append(entry)

    return {
        "exercises": exercises,
        "coverage": {"resolved": resolved, "total": len(exercises)},
    }
