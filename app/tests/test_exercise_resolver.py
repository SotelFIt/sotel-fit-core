"""
LIB-005 Parte A - resolucao name -> identidade canonica (dominio Biblioteca).

Prova: normalizacao generica; casamento deterministico contra name + aliases;
precedencia do canonico; somente exercicios ativos participam.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.exercise import Exercise
from services.exercise_resolver import normalize_name, resolve_exercise, build_index, resolve_with_index


def _session():
    eng = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(eng, tables=[Exercise.__table__])
    return sessionmaker(bind=eng)()


def _ex(slug, name, aliases=None, active=True, muscle='Perna'):
    return Exercise(slug=slug, name=name, aliases=aliases or [], primary_muscle=muscle,
                    equipment='Maquina', level='iniciante', is_active=active)


def test_normalize_remove_acento_parenteses_pontuacao_e_prefixo():
    assert normalize_name('- Leg Press (pés altos)') == 'leg press'
    assert normalize_name('Puxador Frente') == 'puxador frente'
    assert normalize_name('Extensão de Quadríceps (Máquina)') == 'extensao de quadriceps'
    assert normalize_name('Tríceps na Corda') == 'triceps na corda'


def test_resolve_canonico_ignora_qualificadores():
    db = _session()
    db.add(_ex('leg-press', 'Leg Press'))
    db.commit()
    assert resolve_exercise(db, 'Leg press (se disponível)') == {'slug': 'leg-press', 'match': 'canonical'}
    assert resolve_exercise(db, 'Leg Press (Ângulo 45°)') == {'slug': 'leg-press', 'match': 'canonical'}


def test_resolve_por_alias():
    db = _session()
    db.add(_ex('puxada-frontal', 'Puxada Frontal',
              aliases=['Puxador Frente', 'Pull Down', 'Puxada na Barra']))
    db.commit()
    assert resolve_exercise(db, 'Puxador Frente') == {'slug': 'puxada-frontal', 'match': 'alias'}
    assert resolve_exercise(db, 'PULL DOWN') == {'slug': 'puxada-frontal', 'match': 'alias'}


def test_nome_desconhecido_nao_resolve():
    db = _session()
    db.add(_ex('leg-press', 'Leg Press'))
    db.commit()
    assert resolve_exercise(db, 'Superman Modificado') is None


def test_inativo_nao_participa_da_resolucao():
    db = _session()
    db.add(_ex('stiff', 'Stiff', active=False))
    db.commit()
    assert resolve_exercise(db, 'Stiff') is None


def test_canonico_tem_precedencia_sobre_alias():
    # 'remada' e nome canonico de um e alias de outro -> vence o canonico.
    db = _session()
    db.add(_ex('remada-sentada', 'Remada', muscle='Costas'))
    db.add(_ex('outro', 'Outro Exercicio', aliases=['Remada'], muscle='Costas'))
    db.commit()
    assert resolve_exercise(db, 'Remada') == {'slug': 'remada-sentada', 'match': 'canonical'}
