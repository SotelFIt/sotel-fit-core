"""
import_substitution_rules - importer das regras direcionais de substituicao (LIB-013B).

Espelha o contrato do import_exercise_catalog: dry-run por padrao, idempotente,
valida TUDO antes de tocar em qualquer coisa, e nunca corrige silenciosamente.

Fonte canonica: app/data/exercise_substitution_rules.json.
Relacoes sao ARESTAS: nao vivem no catalogo de exercicios, e o catalogo nao as
declara. Uma unica fonte no repo, comparada contra a producao.

Statuses por regra:
  would_create   - ausente na producao (em --apply seria criada)
  skipped_equal  - ja existe identica
  conflict       - existe com relation_type/rationale/condition diferentes
  invalid        - viola o contrato (rationale vazio, contextual sem condition, tipo invalido)
  missing_target - source ou target nao existe na Biblioteca
  duplicate      - o mesmo par (source,target) aparece duas vezes no arquivo
  self_reference - source == target

Uso:
  SOTEL_ADMIN_API_KEY=<segredo-fora-do-comando> \\
  python tools/import_substitution_rules.py --rules app/data/exercise_substitution_rules.json \\
      --base-url https://... --dry-run
"""
import argparse
import json
import os
import sys
from typing import Dict, List

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))
from services.substitution_rules import validate_rule  # noqa: E402

API_KEY_ENV = "SOTEL_ADMIN_API_KEY"
CAMPOS_COMPARADOS = ("relation_type", "rationale", "condition", "is_active")


class RulesError(Exception):
    pass


def load_rules(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "rules" not in data:
        raise RulesError("arquivo invalido: objeto sem chave 'rules'.")
    if not isinstance(data["rules"], list):
        raise RulesError("arquivo invalido: 'rules' nao e uma lista.")
    declarado = (data.get("_meta") or {}).get("count")
    if declarado is not None and declarado != len(data["rules"]):
        raise RulesError(f"_meta.count={declarado} nao bate com {len(data['rules'])} regras.")
    return data


def classify(rules: List[dict], exercicios: set, producao: Dict[tuple, dict]) -> List[dict]:
    """Uma linha de resultado por regra do arquivo. Nao escreve nada."""
    vistos = set()
    out = []
    for r in rules:
        source, target = r.get("source"), r.get("target")
        chave = (source, target)
        item = {"source": source, "target": target}

        if source == target:
            out.append({**item, "status": "self_reference"})
            continue
        if chave in vistos:
            out.append({**item, "status": "duplicate"})
            continue
        vistos.add(chave)
        if source not in exercicios or target not in exercicios:
            faltando = [s for s in (source, target) if s not in exercicios]
            out.append({**item, "status": "missing_target", "detalhe": faltando})
            continue
        erro = validate_rule(r.get("relation_type"), r.get("rationale"), r.get("condition"))
        if erro:
            out.append({**item, "status": "invalid", "detalhe": erro})
            continue

        atual = producao.get(chave)
        if atual is None:
            out.append({**item, "status": "would_create"})
            continue
        diffs = [c for c in CAMPOS_COMPARADOS if (atual.get(c) or None) != (r.get(c) if c != "is_active" else r.get(c, True))]
        out.append({**item, "status": "skipped_equal" if not diffs else "conflict",
                    **({"diffs": diffs} if diffs else {})})
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rules", required=True)
    p.add_argument("--base-url", required=True)
    modo = p.add_mutually_exclusive_group()
    modo.add_argument("--dry-run", action="store_true", help="padrao; nao escreve")
    modo.add_argument("--apply", action="store_true", help="reservado; escrita ocorre via migration aditiva")
    args = p.parse_args()

    data = load_rules(args.rules)
    api_key = os.environ.get(API_KEY_ENV)
    headers = {"x-api-key": api_key} if api_key else {}
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=30) as client:
        r = client.get("/exercises")
        r.raise_for_status()
        exercicios = {e["slug"] for e in r.json()}
        r = client.get("/admin/exercises/substitution-rules")
        r.raise_for_status()
        producao = {(x["source"], x["target"]): x for x in r.json()}

    resultados = classify(data["rules"], exercicios, producao)
    counts: Dict[str, int] = {}
    for x in resultados:
        counts[x["status"]] = counts.get(x["status"], 0) + 1

    orfas = [f"{k[0]}->{k[1]}" for k in producao
             if k not in {(x["source"], x["target"]) for x in data["rules"]}]

    modo_txt = "apply" if args.apply else "dry-run"
    print(f"[{modo_txt}] arquivo={len(data['rules'])} producao={len(producao)} "
          + " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
          + f" orfas_em_producao={len(orfas)}")
    for x in resultados:
        if x["status"] not in ("skipped_equal",):
            print(f"  {x['status']:<15} {x['source']} -> {x['target']} {x.get('detalhe') or x.get('diffs') or ''}")
    for o in orfas:
        print(f"  orfa_em_producao {o} (existe no banco e nao no arquivo canonico)")

    if args.apply:
        print("ERRO: --apply nao e suportado. As regras entram por migration ADITIVA "
              "(app/migrate.py), nunca por escrita direta do importer.")
        return 2
    ruins = {"invalid", "missing_target", "duplicate", "self_reference", "conflict"}
    return 1 if (set(counts) & ruins) or orfas else 0


if __name__ == "__main__":
    sys.exit(main())
