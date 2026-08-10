"""
LIB-012A - trava do PADRAO EDITORIAL da Knowledge Layer.

A LIB-011 fechou a IDENTIDADE da Biblioteca ("qual exercicio e esse?").
A LIB-012 responde "o que o sistema sabe sobre esse exercicio?" - e conhecimento
so vale se for consistente. Estes testes travam o FORMATO, nunca o conteudo:

- instructions: 5 passos numerados 1..5 (posicao inicial, preparacao, execucao,
  controle, retorno). Vale tambem para isometria, onde o passo 3/4 e a sustentacao.
- cautions: 2..5 cuidados especificos do movimento.
- common_errors: 3..6 erros OBSERVAVEIS.
- secondary_muscles: subconjunto do vocabulario controlado de _meta.taxonomia.
  primary_muscle, no maximo 3, sem repetir o primary_muscle do proprio exercicio.

O piloto da LIB-012A (5 exercicios) e um PISO, nao um teto: a LIB-012B preenche
os 28 restantes e estes testes continuam validos sem alteracao.
"""
import json
import os
import re

import pytest

CATALOGO = os.path.join(os.path.dirname(__file__), "..", "data", "exercise_catalog_sprint1.json")

# Piso: preenchidos na LIB-012A. Cobrem peitoral, costas, inferiores, ombros e core.
PILOTO_LIB_012A = {
    "supino-reto",
    "remada-sentada",
    "leg-press",
    "desenvolvimento",
    "prancha-frontal",
}


@pytest.fixture(scope="module")
def catalogo():
    with open(CATALOGO, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def com_conhecimento(catalogo):
    return [e for e in catalogo["exercises"] if e.get("instructions")]


def test_piloto_da_lib_012a_esta_preenchido(com_conhecimento):
    slugs = {e["slug"] for e in com_conhecimento}
    assert PILOTO_LIB_012A <= slugs, f"piloto sem conhecimento: {PILOTO_LIB_012A - slugs}"


def test_instructions_tem_cinco_passos_numerados(com_conhecimento):
    for e in com_conhecimento:
        passos = [l for l in e["instructions"].split("\n") if l.strip()]
        assert len(passos) == 5, f"{e['slug']}: {len(passos)} passos"
        for i, passo in enumerate(passos):
            assert re.match(rf"^{i + 1}\. \S", passo), f"{e['slug']}: passo {i + 1} malformado"


def test_cautions_e_common_errors_dentro_do_padrao(com_conhecimento):
    for e in com_conhecimento:
        assert 2 <= len(e["cautions"]) <= 5, f"{e['slug']}: {len(e['cautions'])} cautions"
        assert 3 <= len(e["common_errors"]) <= 6, f"{e['slug']}: {len(e['common_errors'])} erros"
        for texto in e["cautions"] + e["common_errors"]:
            assert texto.strip() and texto[0].isupper(), f"{e['slug']}: item mal formatado {texto!r}"


def test_secondary_muscles_usa_o_vocabulario_controlado(catalogo, com_conhecimento):
    """A lista PODE ser vazia: movimentos de isolamento (extensora, roscas, panturrilha,
    elevacao lateral) nao tem musculo secundario relevante dentro da taxonomia, e
    inventar um so para preencher o campo violaria a regra de nao inflar."""
    vocabulario = set(catalogo["_meta"]["taxonomia"]["primary_muscle"])
    for e in com_conhecimento:
        # o catalogo OMITE o campo quando ele e a lista vazia (convencao do arquivo)
        secundarios = e.get("secondary_muscles", [])
        fora = set(secundarios) - vocabulario
        assert not fora, f"{e['slug']}: fora da taxonomia {fora}"
        assert len(secundarios) <= 3, f"{e['slug']}: {len(secundarios)} secundarios (inflado)"
        assert e["primary_muscle"] not in secundarios, f"{e['slug']}: primary repetido"
        assert len(set(secundarios)) == len(secundarios), f"{e['slug']}: secundarios duplicados"


def test_conhecimento_nao_prescreve_carga_nem_volume(com_conhecimento):
    """Carga/serie/repeticao pertencem ao PLANO, nunca a Biblioteca."""
    proibido = re.compile(r"\b\d+\s?(kg|quilos)\b|\b\d+\s?x\s?\d+\b|\b\d+\s?repeticoes\b", re.I)
    for e in com_conhecimento:
        blob = " ".join([e["instructions"], *e["cautions"], *e["common_errors"]])
        achado = proibido.search(blob)
        assert not achado, f"{e['slug']}: prescricao de carga/volume {achado.group(0)!r}"


def test_conhecimento_nao_faz_afirmacao_clinica(com_conhecimento):
    """A Biblioteca orienta execucao; nao diagnostica nem trata."""
    clinico = ["tendinite", "hernia", "bursite", "artrose", "diagnostic", "tratamento",
               "patolog", "fisioterap"]
    for e in com_conhecimento:
        blob = " ".join([e["instructions"], *e["cautions"], *e["common_errors"]]).lower()
        for termo in clinico:
            assert termo not in blob, f"{e['slug']}: afirmacao clinica {termo!r}"


def test_midia_segue_fora_de_escopo(catalogo):
    """`media` continua reservada a uma missao posterior. `approved_substitutions`
    saiu desta reserva na LIB-013A e passou a ser coberto por test_substitution_graph.py."""
    for e in catalogo["exercises"]:
        assert not e.get("media"), f"{e['slug']}: midia fora de escopo"
