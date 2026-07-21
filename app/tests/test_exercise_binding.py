"""
LIB-005 Parte B - binding prescricao -> exercicio (build_enrichment).

Prova sobre plano REAL de producao (client 12): cobertura, resolucao por
canonico e por alias, unresolved como estado valido, e idempotencia.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.exercise import Exercise
from services.exercise_binding import build_enrichment, compute_source_hash

FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def _session():
    eng = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(eng, tables=[Exercise.__table__])
    return sessionmaker(bind=eng)()


def _ex(slug, name, aliases=None, muscle='Perna'):
    return Exercise(slug=slug, name=name, aliases=aliases or [], primary_muscle=muscle,
                    equipment='Maquina', level='iniciante', is_active=True)


def _seed_catalogo_min(db):
    """Subconjunto do catalogo canonico suficiente para o plano 12."""
    db.add_all([
        _ex('leg-press', 'Leg Press'),
        _ex('cadeira-extensora', 'Cadeira Extensora'),
        _ex('abdominal-maquina', 'Abdominal na Máquina', muscle='Core'),
        _ex('prancha-frontal', 'Prancha Frontal', aliases=['Prancha Estática'], muscle='Core'),
        _ex('supino-reto', 'Supino Reto', aliases=['Supino com Haltere'], muscle='Peito'),
        _ex('remada-sentada', 'Remada Sentada', muscle='Costas'),
        _ex('rosca-direta', 'Rosca Direta', muscle='Biceps'),
        _ex('triceps-corda', 'Tríceps na Corda', muscle='Triceps'),
        _ex('hip-thrust', 'Hip Thrust', muscle='Gluteos'),
        _ex('stiff', 'Stiff', muscle='Posterior'),
    ])
    db.commit()


def _plan_12():
    with open(os.path.join(FIX, 'real_plans.json'), encoding='utf-8') as f:
        return json.load(f)['12']


def test_cobertura_e_resolucoes_no_plano_real_12():
    db = _session()
    _seed_catalogo_min(db)
    enr = build_enrichment(db, _plan_12())

    assert enr['coverage']['total'] == 15
    assert enr['coverage']['resolved'] == 11

    by_name = {e['name_raw']: e for e in enr['exercises']}
    # canonico com qualificador
    assert by_name['Leg Press (Ângulo 45°)']['library_ref'] == 'leg-press'
    assert by_name['Leg Press (Ângulo 45°)']['status'] == 'resolved'
    # por alias
    assert by_name['Prancha Estática']['library_ref'] == 'prancha-frontal'
    assert by_name['Prancha Estática']['match'] == 'alias'
    assert by_name['Supino com Haltere']['library_ref'] == 'supino-reto'
    # unresolved (estado valido, nao quebra)
    for nome in ['Leg Curl', 'Mobilidade de Coluna Torácica', 'Reverse Sled', 'Superman Modificado']:
        assert by_name[nome]['status'] == 'unresolved'
        assert by_name[nome]['library_ref'] is None


def test_occurrence_key_presente_e_estavel():
    db = _session()
    _seed_catalogo_min(db)
    enr = build_enrichment(db, _plan_12())
    keys = [e['occurrence_key'] for e in enr['exercises']]
    assert all(keys)
    assert len(keys) == len(enr['exercises'])  # uma chave por ocorrencia


def test_idempotencia_mesmo_texto_gera_mesma_saida_e_hash():
    db = _session()
    _seed_catalogo_min(db)
    txt = _plan_12()
    assert build_enrichment(db, txt) == build_enrichment(db, txt)
    assert compute_source_hash(txt) == compute_source_hash(txt)
    assert compute_source_hash(txt) != compute_source_hash(txt + ' ')


def test_biblioteca_vazia_resolve_zero_sem_quebrar():
    db = _session()  # nenhum exercicio
    enr = build_enrichment(db, _plan_12())
    assert enr['coverage']['resolved'] == 0
    assert enr['coverage']['total'] == 15
    assert all(e['status'] == 'unresolved' for e in enr['exercises'])
