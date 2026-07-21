"""
LIB-005 - valida o catalogo de referencia e a cobertura sobre TODOS os planos reais.

Carrega `app/data/exercise_seed_catalog.json` numa Biblioteca em memoria e roda o
binding sobre os planos reais congelados. Trava a cobertura esperada (numeros do
Gate 0) e a integridade do catalogo. Cobertura parcial e ESPERADA e valida:
unresolved e estado legitimo (typos/variantes fora do seed minimo).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.exercise import Exercise
from schemas.exercise import ExerciseLevel  # noqa: F401 (documenta o enum)
from services.exercise_binding import build_enrichment
from services.exercise_resolver import normalize_name

CATALOG = os.path.join(os.path.dirname(__file__), '..', 'data', 'exercise_seed_catalog.json')
FIX = os.path.join(os.path.dirname(__file__), 'fixtures')
LEVELS = {'iniciante', 'intermediario', 'avancado'}


def _catalog():
    with open(CATALOG, encoding='utf-8') as f:
        return json.load(f)['exercises']


def _session_with_catalog():
    eng = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(eng, tables=[Exercise.__table__])
    db = sessionmaker(bind=eng)()
    for e in _catalog():
        db.add(Exercise(
            slug=e['slug'], name=e['name'], aliases=e.get('aliases', []),
            primary_muscle=e['primary_muscle'], equipment=e['equipment'],
            level=e['level'], is_active=True,
        ))
    db.commit()
    return db


def _plans():
    with open(os.path.join(FIX, 'real_plans.json'), encoding='utf-8') as f:
        return json.load(f)


def test_catalogo_integro():
    cat = _catalog()
    slugs = [e['slug'] for e in cat]
    assert len(slugs) == len(set(slugs)), 'slugs duplicados no catalogo'
    canon = {normalize_name(e['name']): e['slug'] for e in cat}
    for e in cat:
        for campo in ('slug', 'name', 'primary_muscle', 'equipment', 'level'):
            assert e.get(campo), f"{e.get('slug')}: campo obrigatorio ausente: {campo}"
        assert e['level'] in LEVELS, f"{e['slug']}: level invalido"
        # nenhum alias pode colidir com o nome canonico de OUTRO exercicio (determinismo)
        for a in e.get('aliases', []):
            owner = canon.get(normalize_name(a))
            assert owner in (None, e['slug']), f"alias '{a}' colide com canonico de {owner}"


def test_cobertura_esperada_por_plano_real():
    db = _session_with_catalog()
    plans = _plans()
    esperado = {
        '12': (11, 15),
        '19': (9, 19),
        '23': (10, 21),
        '24': (11, 11),
        '36': (15, 20),
        'SOTEL': (13, 28),
    }
    for k, (res, tot) in esperado.items():
        enr = build_enrichment(db, plans[k])
        cov = enr['coverage']
        assert (cov['resolved'], cov['total']) == (res, tot), \
            f"plano {k}: cobertura {cov} != esperado {(res, tot)}"


def test_alias_resolve_variacao_conhecida_no_sotel():
    db = _session_with_catalog()
    enr = build_enrichment(db, _plans()['SOTEL'])
    by_name = {e['name_raw']: e for e in enr['exercises']}
    # 'Puxador Frente' e 'Pull Down' -> puxada-frontal por ALIAS
    assert by_name['Puxador Frente']['library_ref'] == 'puxada-frontal'
    assert by_name['Puxador Frente']['match'] == 'alias'
    assert by_name['Pull Down']['library_ref'] == 'puxada-frontal'
