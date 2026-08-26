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

from models.exercise import Exercise

from services.workout_extract import extract_exercises
from services.exercise_resolver import build_index, resolve_with_index, normalize_name


def compute_source_hash(published_content: Optional[str]) -> str:
    return hashlib.sha256((published_content or "").encode("utf-8")).hexdigest()


def _occurrence_key(norm: str, ordinal: int, context_path: str) -> str:
    """Identidade estavel POR SNAPSHOT (funcao pura do conteudo, nao posicional):
    forma normalizada + ordinal da ocorrencia desse nome nesse contexto + contexto."""
    raw = f"{norm}#{ordinal}@{context_path}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def build_enrichment(
    db: Session,
    published_content: Optional[str],
    bindings: Optional[dict] = None,
) -> dict:
    """Enriquecimento derivado do texto publicado:
    { "exercises": [ {occurrence_key, name_raw, context_path, library_ref, status, match?} ],
      "coverage": {resolved, total} }.

    `bindings` sao os vinculos ESCOLHIDOS por um profissional no administrativo,
    no formato {occurrence_key: slug}. Eles tem precedencia sobre a resolucao
    automatica e recebem `status: "manual"`.

    Por que precedencia: a resolucao automatica casa por nome e alias
    normalizados. Ela acerta muito, mas quando erra, erra em silencio — e hoje
    57% das ocorrencias dos planos reais nao resolvem para exercicio nenhum.
    Escolha humana nao pode ser sobrescrita por heuristica na proxima
    republicacao.
    """
    items = extract_exercises(published_content or "")
    index = build_index(db)
    bindings = bindings or {}
    # Só aceita slug que EXISTE. Vinculo apontando para exercicio inexistente e
    # pior que vinculo nenhum: o cliente pediria uma orientacao fantasma.
    validos = {r[0] for r in db.query(Exercise.slug).all()} if bindings else set()

    exercises = []
    seen = {}
    resolved = 0
    for it in items:
        norm = normalize_name(it["name"])
        ctx = it["context_path"]
        ordinal = seen.get((norm, ctx), 0)
        seen[(norm, ctx)] = ordinal + 1

        chave = _occurrence_key(norm, ordinal, ctx)
        escolhido = bindings.get(chave)

        if escolhido and escolhido in validos:
            # Escolha humana: vale, e fica marcada como tal.
            entry = {
                "occurrence_key": chave,
                "name_raw": it["name"],
                "context_path": ctx,
                "library_ref": escolhido,
                "status": "manual",
                "match": "manual",
            }
            resolved += 1
            exercises.append(entry)
            continue

        hit = resolve_with_index(index, it["name"])
        entry = {
            "occurrence_key": chave,
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
