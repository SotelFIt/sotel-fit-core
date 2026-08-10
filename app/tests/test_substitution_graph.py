"""
LIB-013A - integridade e INTENCAO do grafo de substituicoes.

A LIB-011 respondeu "qual exercicio e esse?", a LIB-012 respondeu "como ele
funciona?". Aqui comeca "o que pode ocupar o lugar dele?".

O campo `approved_substitutions` guarda apenas slugs. A API ja garante, na
escrita, que nao ha duplicata, autorreferencia nem slug inexistente
(`_validate_substitutions`). Estes testes cobrem o que a API NAO garante: que o
grafo gravado corresponde as DECISOES tomadas na LIB-013A.

Duas decisoes estruturais ficam travadas aqui:

1. Substituicao NAO e "mesmo musculo". `supino-maquina` e `voador` tem primary,
   equipment e level IDENTICOS e mesmo assim nao se substituem: um e composto de
   empurrar, o outro e isolador de aducao. Este e o teste NEGATIVO da missao.

2. Substituicao NAO e automaticamente simetrica. `agachamento-livre` aceita
   `leg-press` (a maquina reduz a demanda de estabilidade); o inverso exige
   estabilidade e tecnica adicionais e por isso NAO foi gravado. Espelhar a
   aresta seria inventar uma equivalencia que ninguem validou.

Aresta mutua (2-ciclo) NAO e defeito: dois exercicios podem se substituir nos
dois sentidos, e e isso que `supino-reto` <-> `supino-com-halteres` registra.
"""
import json
import os

import pytest

CATALOGO = os.path.join(os.path.dirname(__file__), "..", "data", "exercise_catalog_sprint1.json")

SIMETRICAS_INTENCIONAIS = [("supino-reto", "supino-com-halteres")]
DIRECIONAIS_INTENCIONAIS = [("agachamento-livre", "leg-press")]
NAO_SUBSTITUEM = [("supino-maquina", "voador")]


@pytest.fixture(scope="module")
def exercicios():
    with open(CATALOGO, encoding="utf-8") as f:
        return {e["slug"]: e for e in json.load(f)["exercises"]}


@pytest.fixture(scope="module")
def arestas(exercicios):
    return [(s, alvo) for s, e in exercicios.items()
            for alvo in e.get("approved_substitutions", [])]


def test_toda_substituicao_aponta_para_exercicio_existente(exercicios, arestas):
    for origem, alvo in arestas:
        assert alvo in exercicios, f"{origem} -> {alvo}: slug inexistente"


def test_nenhuma_autorreferencia(arestas):
    for origem, alvo in arestas:
        assert origem != alvo, f"{origem}: autorreferencia"


def test_nenhuma_duplicata(exercicios):
    for slug, e in exercicios.items():
        subs = e.get("approved_substitutions", [])
        assert len(subs) == len(set(subs)), f"{slug}: substituicoes duplicadas"


def test_substituicao_nunca_aponta_para_exercicio_inativo(exercicios, arestas):
    for origem, alvo in arestas:
        assert exercicios[alvo].get("is_active", True), f"{origem} -> {alvo}: alvo inativo"


def test_par_simetrico_intencional_existe_nos_dois_sentidos(exercicios):
    for a, b in SIMETRICAS_INTENCIONAIS:
        assert b in exercicios[a].get("approved_substitutions", []), f"{a} -> {b} ausente"
        assert a in exercicios[b].get("approved_substitutions", []), f"{b} -> {a} ausente"


def test_relacao_direcional_nao_e_espelhada(exercicios):
    """O inverso NAO deve existir: espelhar seria afirmar uma equivalencia nao validada."""
    for origem, alvo in DIRECIONAIS_INTENCIONAIS:
        assert alvo in exercicios[origem].get("approved_substitutions", []), f"{origem} -> {alvo} ausente"
        assert origem not in exercicios[alvo].get("approved_substitutions", []), (
            f"{alvo} -> {origem} foi espelhado automaticamente; a direcao inversa e CONTEXTUAL"
        )


def test_mesmo_musculo_nao_gera_substituicao(exercicios):
    """Teste NEGATIVO: primary/equipment/level identicos e ainda assim nao se substituem."""
    for a, b in NAO_SUBSTITUEM:
        assert exercicios[a]["primary_muscle"] == exercicios[b]["primary_muscle"]
        assert exercicios[a]["equipment"] == exercicios[b]["equipment"]
        assert b not in exercicios[a].get("approved_substitutions", []), f"{a} -> {b} nao deveria existir"
        assert a not in exercicios[b].get("approved_substitutions", []), f"{b} -> {a} nao deveria existir"


def test_piloto_da_lib_013a_nao_extrapolou(exercicios, arestas):
    """A LIB-013A e um PILOTO: apenas as relacoes de alta confianca foram gravadas.
    Preencher os 33 e a proxima missao, nao esta."""
    envolvidos = {s for aresta in arestas for s in aresta}
    assert envolvidos <= {"supino-reto", "supino-com-halteres", "agachamento-livre", "leg-press"}, (
        f"grafo saiu do escopo do piloto: {sorted(envolvidos)}"
    )
