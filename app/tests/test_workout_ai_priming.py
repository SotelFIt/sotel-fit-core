"""
LIB-009.1 - priming: a Biblioteca de Exercicios participa da geracao ANTES do Claude,
como VOCABULARIO OFICIAL no prompt. Prova:
  (1) Biblioteca preenchida  -> secao presente, nomes canonicos, sem inativos, ordem deterministica;
  (2) Biblioteca vazia       -> helper retorna "", secao ausente, prompt identico ao anterior;
  (3) compatibilidade        -> chamadas antigas de _montar_prompt continuam validas;
  (4) falha de leitura       -> nao propaga; helper retorna "".
SQLite em memoria; sem producao, sem token, sem rede, sem Anthropic (o modulo so
importa o SDK dentro de gerar_treino_base, nao no topo).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from models.exercise import Exercise
from services.workout_ai import _carregar_vocabulario_biblioteca, _montar_prompt

SECAO = "VOCABULARIO OFICIAL DA BIBLIOTECA DE EXERCICIOS"
DADOS = {"objetivo": "emagrecimento", "nivel_treino": "iniciante", "dias_treino": "3"}


def _db(exercicios=()):
    eng = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(eng, tables=[Exercise.__table__])
    db = sessionmaker(bind=eng)()
    for ex in exercicios:
        db.add(Exercise(**ex))
    db.commit()
    return db


def _ex(slug, name, primary_muscle, is_active=True):
    return dict(slug=slug, name=name, primary_muscle=primary_muscle,
                equipment="maquina", level="iniciante", is_active=is_active)


# ---------------- TESTE 1: Biblioteca preenchida ----------------
def test_biblioteca_preenchida_secao_nomes_sem_inativos_ordem():
    db = _db([
        _ex("supino", "Supino Maquina", "peitoral"),
        _ex("flexao", "Flexao de Bracos", "peitoral"),
        _ex("remada", "Remada Sentada", "costas"),
        _ex("inativo", "Exercicio Inativo", "peitoral", is_active=False),
    ])
    vocab = _carregar_vocabulario_biblioteca(db)
    # ordem deterministica: grupos por nome (costas < peitoral); nomes por nome (Flexao < Supino)
    assert vocab == "costas: Remada Sentada\npeitoral: Flexao de Bracos, Supino Maquina"
    # deterministico: repetir da o mesmo resultado
    assert _carregar_vocabulario_biblioteca(db) == vocab

    prompt = _montar_prompt(DADOS, "diretriz X", vocab)
    assert SECAO in prompt
    assert "Flexao de Bracos" in prompt
    assert "Supino Maquina" in prompt
    assert "Remada Sentada" in prompt
    # exercicio inativo NUNCA aparece
    assert "Exercicio Inativo" not in prompt


# ---------------- TESTE 2: Biblioteca vazia ----------------
def test_biblioteca_vazia_helper_vazio_secao_ausente_prompt_identico():
    db = _db([])
    assert _carregar_vocabulario_biblioteca(db) == ""

    prompt_vazio = _montar_prompt(DADOS, "diretriz X", "")
    assert SECAO not in prompt_vazio
    # identico a chamada antiga (2 args): sem bloco vazio, comportamento preservado
    assert prompt_vazio == _montar_prompt(DADOS, "diretriz X")


# ---------------- TESTE 3: compatibilidade ----------------
def test_compat_chamadas_antigas_de_montar_prompt():
    p1 = _montar_prompt(DADOS)            # 1 arg (como nunca existiu, mas default garante)
    p2 = _montar_prompt(DADOS, "")        # 2 args (assinatura anterior)
    p3 = _montar_prompt(DADOS, "", "")    # 3 args com default explicito
    assert p1 == p2 == p3
    assert SECAO not in p1


# ---------------- TESTE 4: falha de leitura ----------------
class _DbFalha:
    def query(self, *a, **k):
        raise RuntimeError("falha simulada de leitura da Biblioteca")


def test_falha_de_leitura_nao_propaga_retorna_vazio():
    # a Biblioteca nunca pode derrubar a geracao
    assert _carregar_vocabulario_biblioteca(_DbFalha()) == ""
