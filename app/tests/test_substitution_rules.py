"""
LIB-013B - contrato das regras direcionais de substituicao.

O teste que motivou esta tabela e `test_direcao_inversa_nao_e_inferida`: com o
modelo antigo (lista de slugs), perguntar "posso trocar leg press por agachamento
livre?" era respondido com SIM porque existia a aresta no sentido CONTRARIO.
Aqui isso e impossivel por construcao - e travado por teste.

Os quatro estados sao o contrato:
  direct/acceptable -> YES · contextual -> DEPENDS · rejected -> NO
  sem regra         -> NOT_EVALUATED  (nunca NO)
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.exercise import Exercise
from models.exercise_substitution import ExerciseSubstitutionRule
from services.substitution_rules import (
    get_substitution_decision,
    projected_substitutions,
    validate_rule,
)

ARQUIVO_REGRAS = os.path.join(os.path.dirname(__file__), "..", "data",
                              "exercise_substitution_rules.json")


def _ex(slug, **kw):
    base = dict(slug=slug, name=slug.replace("-", " ").title(), primary_muscle="peitoral",
                equipment="barra", level="intermediario", is_active=True)
    base.update(kw)
    return Exercise(**base)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    for slug in ("a", "b", "c", "inativo"):
        s.add(_ex(slug, is_active=(slug != "inativo")))
    s.commit()
    yield s
    s.close()


def _id(s, slug):
    return s.query(Exercise).filter(Exercise.slug == slug).one().id


def _regra(s, source, target, relation_type, rationale="porque sim, tecnicamente", condition=None):
    r = ExerciseSubstitutionRule(
        source_exercise_id=_id(s, source), target_exercise_id=_id(s, target),
        relation_type=relation_type, rationale=rationale, condition=condition, is_active=True)
    s.add(r)
    s.commit()
    return r


# ---------------- os quatro estados ----------------

def test_direct_responde_yes(db):
    _regra(db, "a", "b", "direct")
    assert get_substitution_decision(db, "a", "b")["decision"] == "YES"


def test_acceptable_responde_yes(db):
    _regra(db, "a", "b", "acceptable")
    d = get_substitution_decision(db, "a", "b")
    assert d["decision"] == "YES" and d["relation_type"] == "acceptable"


def test_contextual_responde_depends_com_condicao(db):
    _regra(db, "a", "b", "contextual", condition="somente com supervisao")
    d = get_substitution_decision(db, "a", "b")
    assert d["decision"] == "DEPENDS"
    assert d["condition"] == "somente com supervisao"


def test_rejected_responde_no(db):
    _regra(db, "a", "b", "rejected")
    assert get_substitution_decision(db, "a", "b")["decision"] == "NO"


def test_par_sem_regra_responde_not_evaluated(db):
    """Ausencia NUNCA e rejeicao: 'ninguem avaliou' nao autoriza dizer 'nao pode'."""
    d = get_substitution_decision(db, "a", "c")
    assert d["decision"] == "NOT_EVALUATED"
    assert d["relation_type"] is None


# ---------------- direcao ----------------

def test_direcao_inversa_nao_e_inferida(db):
    """O teste que motivou a missao. a->b APPROVED nao autoriza b->a."""
    _regra(db, "a", "b", "acceptable")
    assert get_substitution_decision(db, "a", "b")["decision"] == "YES"
    assert get_substitution_decision(db, "b", "a")["decision"] == "NOT_EVALUATED"


def test_direcao_inversa_pode_ter_decisao_propria(db):
    _regra(db, "a", "b", "acceptable")
    _regra(db, "b", "a", "contextual", condition="so com dominio do padrao")
    assert get_substitution_decision(db, "a", "b")["decision"] == "YES"
    assert get_substitution_decision(db, "b", "a")["decision"] == "DEPENDS"


def test_relacao_simetrica_exige_duas_linhas(db):
    _regra(db, "a", "b", "direct")
    assert get_substitution_decision(db, "b", "a")["decision"] == "NOT_EVALUATED"
    _regra(db, "b", "a", "direct")
    assert get_substitution_decision(db, "b", "a")["decision"] == "YES"
    assert db.query(ExerciseSubstitutionRule).count() == 2


# ---------------- integridade ----------------

def test_par_duplicado_e_rejeitado_pelo_banco(db):
    _regra(db, "a", "b", "direct")
    with pytest.raises(IntegrityError):
        _regra(db, "a", "b", "acceptable")
    db.rollback()


def test_autorreferencia_e_rejeitada_pelo_banco(db):
    with pytest.raises(IntegrityError):
        _regra(db, "a", "a", "direct")
    db.rollback()


def test_target_inexistente_e_rejeitado(db):
    """FK garante o alvo; e o resolver nao inventa decisao para slug fora da Biblioteca."""
    assert "exercise_substitution_rules" in inspect(db.get_bind()).get_table_names()
    fks = inspect(db.get_bind()).get_foreign_keys("exercise_substitution_rules")
    assert {fk["referred_table"] for fk in fks} == {"exercises"}
    assert get_substitution_decision(db, "a", "nao-existe")["decision"] == "NOT_EVALUATED"


def test_contextual_sem_condition_e_invalido():
    assert validate_rule("contextual", "racional", None)
    assert validate_rule("contextual", "racional", "   ")
    assert validate_rule("contextual", "racional", "sob supervisao") is None


def test_rationale_vazio_e_invalido():
    assert validate_rule("direct", "", None)
    assert validate_rule("direct", "   ", None)
    assert validate_rule("bidirectional", "racional", None)


def test_exercicio_inativo_nao_entra_na_projecao(db):
    """Regra continua registrada, mas o alvo inativo nao e recomendado ao cliente."""
    _regra(db, "a", "inativo", "direct")
    assert projected_substitutions(db, _id(db, "a")) == []
    assert projected_substitutions(db, _id(db, "a"), somente_alvo_ativo=False) == ["inativo"]
    assert get_substitution_decision(db, "a", "inativo")["decision"] == "YES"


def test_projecao_usa_somente_direct_e_acceptable(db):
    _regra(db, "a", "b", "direct")
    _regra(db, "a", "c", "rejected")
    assert projected_substitutions(db, _id(db, "a")) == ["b"]


def test_identidade_e_knowledge_layer_nao_mudam(db):
    """Registrar relacao nao pode tocar o exercicio."""
    antes = db.query(Exercise).filter(Exercise.slug == "a").one()
    snapshot = (antes.slug, antes.name, antes.primary_muscle, antes.equipment, antes.level,
                antes.instructions, antes.cautions, antes.common_errors, antes.secondary_muscles)
    _regra(db, "a", "b", "direct")
    depois = db.query(Exercise).filter(Exercise.slug == "a").one()
    assert (depois.slug, depois.name, depois.primary_muscle, depois.equipment, depois.level,
            depois.instructions, depois.cautions, depois.common_errors,
            depois.secondary_muscles) == snapshot


# ---------------- arquivo canonico ----------------

@pytest.fixture(scope="module")
def canonico():
    with open(ARQUIVO_REGRAS, encoding="utf-8") as f:
        return json.load(f)


def test_arquivo_canonico_respeita_o_contrato(canonico):
    vistos = set()
    for r in canonico["rules"]:
        assert r["source"] != r["target"], f"{r['source']}: autorreferencia"
        chave = (r["source"], r["target"])
        assert chave not in vistos, f"{chave}: par duplicado"
        vistos.add(chave)
        assert validate_rule(r["relation_type"], r["rationale"], r.get("condition")) is None, chave
    assert canonico["_meta"]["count"] == len(canonico["rules"])


def test_arquivo_canonico_nao_espelha_relacao_direcional(canonico):
    """agachamento-livre -> leg-press e acceptable; o inverso e contextual, nao copia."""
    por_par = {(r["source"], r["target"]): r["relation_type"] for r in canonico["rules"]}
    assert por_par[("agachamento-livre", "leg-press")] == "acceptable"
    assert por_par[("leg-press", "agachamento-livre")] == "contextual"


def test_catalogo_de_exercicios_nao_declara_mais_substituicoes():
    """Fonte canonica UNICA: relacoes vivem no arquivo de regras, nao no catalogo."""
    catalogo = os.path.join(os.path.dirname(__file__), "..", "data", "exercise_catalog_sprint1.json")
    with open(catalogo, encoding="utf-8") as f:
        for e in json.load(f)["exercises"]:
            assert not e.get("approved_substitutions"), (
                f"{e['slug']}: substituicao declarada no catalogo (fonte duplicada)"
            )


# ---------------- importer ----------------

def _importer():
    import importlib.util
    caminho = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "import_substitution_rules.py")
    spec = importlib.util.spec_from_file_location("import_substitution_rules", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def imp():
    return _importer()


def _regra_arquivo(source, target, relation_type="direct", rationale="racional tecnico", condition=None):
    return {"source": source, "target": target, "relation_type": relation_type,
            "rationale": rationale, "condition": condition, "is_active": True}


def test_importer_detecta_todos_os_status(imp):
    exercicios = {"a", "b", "c"}
    producao = {
        ("a", "b"): {"relation_type": "direct", "rationale": "racional tecnico",
                     "condition": None, "is_active": True},
        ("b", "c"): {"relation_type": "direct", "rationale": "outro racional",
                     "condition": None, "is_active": True},
    }
    arquivo = [
        _regra_arquivo("a", "b"),                                   # skipped_equal
        _regra_arquivo("b", "c", rationale="racional tecnico"),      # conflict (rationale mudou)
        _regra_arquivo("a", "c"),                                   # would_create
        _regra_arquivo("a", "fantasma"),                            # missing_target
        _regra_arquivo("a", "a"),                                   # self_reference
        _regra_arquivo("c", "a", "contextual"),                      # invalid (sem condition)
        _regra_arquivo("a", "c"),                                   # duplicate
    ]
    status = [x["status"] for x in imp.classify(arquivo, exercicios, producao)]
    assert status == ["skipped_equal", "conflict", "would_create", "missing_target",
                      "self_reference", "invalid", "duplicate"]


def test_importer_e_idempotente(imp, canonico):
    """Rodar duas vezes sobre a mesma producao da o mesmo resultado, tudo skipped_equal."""
    exercicios = {r["source"] for r in canonico["rules"]} | {r["target"] for r in canonico["rules"]}
    producao = {(r["source"], r["target"]): r for r in canonico["rules"]}
    for _ in range(2):
        res = imp.classify(canonico["rules"], exercicios, producao)
        assert {x["status"] for x in res} == {"skipped_equal"}


def test_importer_recusa_apply(imp):
    """Escrita e por migration aditiva; o importer nao grava relacao."""
    assert "--apply nao e suportado" in open(
        os.path.join(os.path.dirname(__file__), "..", "..", "tools", "import_substitution_rules.py"),
        encoding="utf-8").read()
