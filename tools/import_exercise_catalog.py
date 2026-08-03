#!/usr/bin/env python3
"""
LIB-007A - Importador seguro, idempotente e auditavel da Biblioteca de Exercicios.

Consome EXCLUSIVAMENTE a API admin oficial ja existente:
  GET  /exercises            (lista, autenticada)
  GET  /exercises/{slug}
  POST /admin/exercises      (criacao, require_admin via x-api-key)

Nunca escreve no banco diretamente, nunca usa SQL, nao cria endpoint/bulk-insert.
Dry-run por padrao. Escrita apenas com --apply. A chave admin vem SOMENTE da env
SOTEL_ADMIN_API_KEY, enviada como header x-api-key; nunca por argumento, nunca
exibida, nunca gravada em relatorio/log.

Validacao reutiliza o dominio oficial: schemas.exercise.ExerciseCreate e
services.exercise_resolver.normalize_name (sem duplicar regras).

Uso:
  python tools/import_exercise_catalog.py --catalog app/data/exercise_catalog_sprint1.json \\
      --base-url https://EXEMPLO --dry-run
  SOTEL_ADMIN_API_KEY=<segredo-fora-do-comando> \\
  python tools/import_exercise_catalog.py --catalog ... --base-url https://EXEMPLO --apply --limit 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import httpx

# Dominio oficial (reutilizado, nunca duplicado)
_APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, _APP_DIR)
from schemas.exercise import ExerciseBase, ExerciseCreate  # noqa: E402
from services.exercise_resolver import normalize_name  # noqa: E402

ALLOWED_KEYS = set(ExerciseBase.model_fields.keys())  # campos aceitos no payload
COMPARE_FIELDS = list(ExerciseBase.model_fields.keys())  # ignora id/created_at/updated_at
# LIB-011B: 25 da Sprint 1 + 4 incorporados de producao (crossover,
# crucifixo-com-halteres, supino-inclinado, supino-reto).
SPRINT1_EXPECTED_COUNT = 29
API_KEY_ENV = "SOTEL_ADMIN_API_KEY"

# Timeouts curtos: leitura pode ter retry limitado; POST nunca entra em loop.
DEFAULT_TIMEOUT = httpx.Timeout(15.0)
GET_RETRIES = 2


class CatalogError(Exception):
    """Erro de validacao do catalogo. Bloqueia qualquer escrita."""


# --------------------------------------------------------------------------- #
# Catalogo: carga e validacao (Gate 4)
# --------------------------------------------------------------------------- #

def load_catalog(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_catalog(catalog: dict, *, expected_count: int = SPRINT1_EXPECTED_COUNT) -> List[dict]:
    """Valida TODO o catalogo antes de qualquer request. Retorna a lista de
    payloads canonicos (ExerciseCreate.model_dump()). Levanta CatalogError com
    mensagem explicita em qualquer violacao. NAO corrige silenciosamente."""
    if not isinstance(catalog, dict) or "exercises" not in catalog:
        raise CatalogError("catalogo invalido: objeto sem chave 'exercises'.")
    entries = catalog["exercises"]
    if not isinstance(entries, list):
        raise CatalogError("catalogo invalido: 'exercises' nao e uma lista.")
    if expected_count is not None and len(entries) != expected_count:
        raise CatalogError(f"catalogo deve ter exatamente {expected_count} exercicios; encontrou {len(entries)}.")

    payloads: List[dict] = []
    canon_norm_to_slug: Dict[str, str] = {}
    alias_norm_to_slug: Dict[str, str] = {}
    seen_slugs: set = set()

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise CatalogError(f"exercicio #{i}: nao e um objeto.")
        extra = set(entry.keys()) - ALLOWED_KEYS
        if extra:
            raise CatalogError(f"exercicio #{i} (slug={entry.get('slug')!r}): campos inesperados {sorted(extra)}.")
        # Validacao de contrato pelo dominio (obrigatorios, enum de nivel, slug URL-safe, midia)
        try:
            model = ExerciseCreate(**entry)
        except Exception as e:  # ValidationError do pydantic
            raise CatalogError(f"exercicio #{i} (slug={entry.get('slug')!r}) rejeitado por ExerciseCreate: {e}") from None
        payload = model.model_dump()
        slug = payload["slug"]

        if slug in seen_slugs:
            raise CatalogError(f"slug duplicado no catalogo: {slug!r}.")
        seen_slugs.add(slug)

        name = payload["name"]
        if not name.strip():
            raise CatalogError(f"slug={slug!r}: nome canonico vazio.")
        canon_norm = normalize_name(name)
        if not canon_norm:
            raise CatalogError(f"slug={slug!r}: nome canonico normaliza para vazio.")
        if canon_norm in canon_norm_to_slug:
            raise CatalogError(
                f"nome canonico normalizado duplicado: {name!r} (slug={slug!r}) colide com slug="
                f"{canon_norm_to_slug[canon_norm]!r}."
            )
        canon_norm_to_slug[canon_norm] = slug

        # Aliases: sem vazio, sem duplicata normalizada interna, != canonico, sem colisao cruzada
        seen_alias_norm_local: set = set()
        for alias in payload["aliases"]:
            if not isinstance(alias, str) or not alias.strip():
                raise CatalogError(f"slug={slug!r}: alias vazio nao e permitido.")
            an = normalize_name(alias)
            if not an:
                raise CatalogError(f"slug={slug!r}: alias {alias!r} normaliza para vazio.")
            if an == canon_norm:
                raise CatalogError(f"slug={slug!r}: alias {alias!r} e redundante com o proprio nome canonico.")
            if an in seen_alias_norm_local:
                raise CatalogError(f"slug={slug!r}: alias duplicado (apos normalizacao): {alias!r}.")
            seen_alias_norm_local.add(an)

        payloads.append(payload)

    # 2a passada: colisoes cruzadas de alias (precisa de todos os canonicos ja mapeados)
    for payload in payloads:
        slug = payload["slug"]
        for alias in payload["aliases"]:
            an = normalize_name(alias)
            other = canon_norm_to_slug.get(an)
            if other is not None and other != slug:
                raise CatalogError(f"slug={slug!r}: alias {alias!r} colide com o nome canonico de slug={other!r}.")
            other_alias = alias_norm_to_slug.get(an)
            if other_alias is not None and other_alias != slug:
                raise CatalogError(f"slug={slug!r}: alias {alias!r} colide com alias de slug={other_alias!r}.")
            alias_norm_to_slug[an] = slug

    return payloads


# --------------------------------------------------------------------------- #
# Comparacao / idempotencia (Gate 6)
# --------------------------------------------------------------------------- #

def diff_fields(desired: dict, existing: dict) -> List[str]:
    """Nomes dos campos divergentes, ignorando id/created_at/updated_at.
    Preserva conteudo e ORDEM dos arrays (aliases inclusive)."""
    diffs = []
    for f in COMPARE_FIELDS:
        if desired.get(f) != existing.get(f):
            diffs.append(f)
    return diffs


# --------------------------------------------------------------------------- #
# API (somente a oficial)
# --------------------------------------------------------------------------- #

def fetch_library(client: httpx.Client) -> Dict[str, dict]:
    last_exc = None
    for _ in range(GET_RETRIES):
        try:
            r = client.get("/exercises")
            r.raise_for_status()
            return {e["slug"]: e for e in r.json()}
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last_exc = e
    raise RuntimeError(f"falha ao ler a Biblioteca (GET /exercises): {type(last_exc).__name__}")


def get_by_slug(client: httpx.Client, slug: str) -> Optional[dict]:
    last_exc = None
    for _ in range(GET_RETRIES):
        try:
            r = client.get(f"/exercises/{slug}")
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last_exc = e
    raise RuntimeError(f"falha ao consultar slug={slug} (GET): {type(last_exc).__name__}")


def _classify_after_get(desired: dict, existing: Optional[dict]) -> Optional[str]:
    """Dado o GET pos-tentativa: 'ambiguous_recovered', 'conflict' ou None (ausente)."""
    if existing is None:
        return None
    return "ambiguous_recovered" if not diff_fields(desired, existing) else "conflict"


def _conflict(payload: dict, existing: dict) -> dict:
    return {"status": "conflict", "diffs": diff_fields(payload, existing)}


def _finalize_by_get(client: httpx.Client, payload: dict, *, equal_status: str) -> dict:
    """GET de confirmacao apos uma resposta: equivalente -> equal_status;
    divergente -> conflict; ausente -> failed. (nao faz POST)"""
    existing = get_by_slug(client, payload["slug"])
    if existing is None:
        return {"status": "failed", "reason": "GET nao encontrou o slug apos a resposta"}
    return {"status": equal_status} if not diff_fields(payload, existing) else _conflict(payload, existing)


def _classify_or_failed(client: httpx.Client, payload: dict, *, absent_reason: str) -> dict:
    """GET final quando NAO havera novo POST: equivalente -> ambiguous_recovered;
    divergente -> conflict; ausente -> failed."""
    existing = get_by_slug(client, payload["slug"])
    cls = _classify_after_get(payload, existing)
    if cls == "conflict":
        return _conflict(payload, existing)
    if cls == "ambiguous_recovered":
        return {"status": "ambiguous_recovered"}
    return {"status": "failed", "reason": absent_reason}


def _retry_once(client: httpx.Client, payload: dict) -> dict:
    """A UNICA retentativa permitida (2o POST). Interpreta 201/409/5xx/4xx/timeout
    e NUNCA faz um 3o POST (maximo absoluto de 2 POSTs por slug)."""
    try:
        r2 = client.post("/admin/exercises", json=payload)
    except (httpx.TimeoutException, httpx.TransportError):
        return _classify_or_failed(client, payload, absent_reason="timeout na 2a tentativa; slug ausente")
    if r2.status_code == 201:
        return _finalize_by_get(client, payload, equal_status="created")
    if r2.status_code == 409:
        # 409 na retentativa: o 1o POST pode ter sido efetivado apesar do 5xx -> recuperado
        return _finalize_by_get(client, payload, equal_status="ambiguous_recovered")
    if r2.status_code >= 500:
        return _classify_or_failed(client, payload, absent_reason="5xx persistente na 2a tentativa; slug ausente")
    return {"status": "failed", "reason": f"HTTP {r2.status_code} na 2a tentativa"}


def create_one(client: httpx.Client, payload: dict) -> dict:
    """Cria UM exercicio com semantica segura (Gates 6/7 + LIB-007A.2).
    NUNCA faz loop; no maximo 2 POSTs por slug. status in:
      created, skipped_equal, ambiguous_recovered, conflict, failed
    """
    slug = payload["slug"]
    try:
        r = client.post("/admin/exercises", json=payload)
    except (httpx.TimeoutException, httpx.TransportError):
        # 1o POST ambiguo por timeout: GET; se recuperavel usa, senao UMA retentativa
        existing = get_by_slug(client, slug)
        cls = _classify_after_get(payload, existing)
        if cls == "conflict":
            return _conflict(payload, existing)
        if cls == "ambiguous_recovered":
            return {"status": "ambiguous_recovered"}
        return _retry_once(client, payload)

    if r.status_code == 201:
        return _finalize_by_get(client, payload, equal_status="created")
    if r.status_code == 409:
        # Existente na criacao: igual -> skipped_equal; divergente -> conflict
        return _finalize_by_get(client, payload, equal_status="skipped_equal")
    if r.status_code >= 500:
        existing = get_by_slug(client, slug)
        cls = _classify_after_get(payload, existing)
        if cls == "conflict":
            return _conflict(payload, existing)
        if cls == "ambiguous_recovered":
            return {"status": "ambiguous_recovered"}
        return _retry_once(client, payload)  # ausente -> UNICA retentativa
    # demais 4xx (ex.: 422) -> failed, sem retentativa
    return {"status": "failed", "reason": f"HTTP {r.status_code}"}


# --------------------------------------------------------------------------- #
# Orquestracao
# --------------------------------------------------------------------------- #

def run_import(
    client: httpx.Client,
    catalog: dict,
    *,
    apply: bool = False,
    limit: Optional[int] = None,
    only_slug: Optional[str] = None,
    base_url: str = "",
    expected_count: Optional[int] = SPRINT1_EXPECTED_COUNT,
) -> dict:
    payloads = validate_catalog(catalog, expected_count=expected_count)  # levanta CatalogError se invalido
    library = fetch_library(client)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if apply else "dry-run",
        "catalog_count": len(payloads),
        "base_url": base_url,
        "total_existing": len(library),
        "limit": limit,
        "counts": {k: 0 for k in
                   ["would_create", "created", "skipped_equal", "conflict",
                    "ambiguous_recovered", "failed", "skipped_limit"]},
        "results": [],
    }
    created = 0

    for payload in payloads:
        slug = payload["slug"]
        if only_slug is not None and slug != only_slug:
            continue
        existing = library.get(slug)

        if existing is not None:
            diffs = diff_fields(payload, existing)
            if diffs:
                # Conflito ISOLADO por exercicio: registra, NAO escreve (sem POST/PATCH),
                # e SEGUE para os proximos. Nunca sobrescreve nem transforma em igualdade.
                status, extra = "conflict", {"diffs": diffs}
            else:
                status, extra = "skipped_equal", {}
        else:
            if not apply:
                status, extra = "would_create", {}
            elif limit is not None and created >= limit:
                status, extra = "skipped_limit", {}
            else:
                res = create_one(client, payload)
                status = res.pop("status")
                extra = res
                if status in ("created", "ambiguous_recovered"):
                    created += 1
                # conflict/failed de um item NAO bloqueiam os demais (isolados).

        report["counts"][status] = report["counts"].get(status, 0) + 1
        report["results"].append({"slug": slug, "status": status, **extra})

    report["created_total"] = created
    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_client(base_url: str, api_key: Optional[str]) -> httpx.Client:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key  # nunca logado
    return httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=DEFAULT_TIMEOUT)


def write_report(report: dict, report_dir: str) -> str:
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(report_dir, f"exercise-import-{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return path


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Importador seguro da Biblioteca de Exercicios (LIB-007A).")
    p.add_argument("--catalog", required=True)
    p.add_argument("--base-url", required=True)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="padrao; nao escreve")
    mode.add_argument("--apply", action="store_true", help="habilita escrita (exige SOTEL_ADMIN_API_KEY)")
    p.add_argument("--limit", type=int, default=None, help="max de CRIACOES nesta execucao")
    p.add_argument("--report-dir", default="reports")
    p.add_argument("--only-slug", default=None)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    apply = bool(args.apply)  # default = dry-run

    api_key = os.environ.get(API_KEY_ENV)
    if apply and not api_key:
        # Para ANTES de qualquer request de escrita. Nao pede a chave no terminal.
        print(
            f"ERRO: --apply requer a variavel de ambiente {API_KEY_ENV} definida "
            f"(chave admin; enviada como x-api-key). Nenhuma escrita foi feita.",
            file=sys.stderr,
        )
        return 2

    try:
        catalog = load_catalog(args.catalog)
    except Exception as e:
        print(f"ERRO ao carregar catalogo: {e}", file=sys.stderr)
        return 2

    client = build_client(args.base_url, api_key)
    try:
        report = run_import(
            client, catalog, apply=apply, limit=args.limit,
            only_slug=args.only_slug, base_url=args.base_url,
        )
    except CatalogError as e:
        print(f"CATALOGO INVALIDO (nenhuma escrita): {e}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"ERRO de execucao: {type(e).__name__}: {e}", file=sys.stderr)
        return 4
    finally:
        client.close()

    path = write_report(report, args.report_dir)
    c = report["counts"]
    print(f"[{report['mode']}] catalogo={report['catalog_count']} existentes={report['total_existing']} "
          f"would_create={c['would_create']} created={report['created_total']} skipped_equal={c['skipped_equal']} "
          f"conflict={c['conflict']} ambiguous_recovered={c['ambiguous_recovered']} "
          f"failed={c['failed']} skipped_limit={c['skipped_limit']}")
    print(f"relatorio: {path}")
    # Exit code: 1 se houve conflito/falha (para CI/gate humano), 0 caso contrario.
    return 1 if (c["conflict"] or c["failed"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
