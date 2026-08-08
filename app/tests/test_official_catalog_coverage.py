"""
LIB-011B - cobertura do catalogo OFICIAL sobre os planos reais de producao.

SUBSTITUI `test_seed_catalog_coverage.py`, que media o catalogo OBSOLETO
(`exercise_seed_catalog.json`, 19 itens, taxonomia antiga, divergente de producao).

POR QUE OS NUMEROS MUDARAM (nao houve regressao de codigo):
  o teste antigo media um catalogo que NAO existe em producao. Este mede o catalogo
  OFICIAL (29 itens), que espelha `GET /exercises`. A cobertura caiu de 69/114 (61%)
  para 59/114 (52%) porque o seed continha 12 chaves de resolucao (aliases) que nunca
  foram migradas para o catalogo oficial nem para producao - ex.: 'Puxador Frente',
  'Pull Down', 'Abdominal', 'Prancha Estatica'. Ou seja: 61% era um numero OTIMISTA
  que nao correspondia ao comportamento real do aluno. 52% e a verdade medida.

  Antes (seed)   -> 12:11/15  19:9/19  23:10/21  24:11/11  36:15/20  SOTEL:13/28
  Depois(oficial)-> 12:9/15   19:8/19  23:10/21  24:7/11   36:12/20  SOTEL:13/28

  A decisao de incorporar (ou nao) esses 12 aliases ao catalogo oficial esta
  PENDENTE do Proprietario - por isso o seed foi mantido como evidencia historica.

Cobertura parcial e ESPERADA e valida: `unresolved` e estado legitimo.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.exercise import Exercise
from services.exercise_binding import build_enrichment
from services.exercise_resolver import normalize_name

CATALOG = os.path.join(os.path.dirname(__file__), '..', 'data', 'exercise_catalog_sprint1.json')
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
    """Mesma verificacao do teste antigo, agora sobre a fonte OFICIAL."""
    cat = _catalog()
    slugs = [e['slug'] for e in cat]
    assert len(slugs) == len(set(slugs)), 'slugs duplicados no catalogo'
    canon = {normalize_name(e['name']): e['slug'] for e in cat}
    for e in cat:
        for campo in ('slug', 'name', 'primary_muscle', 'equipment', 'level'):
            assert e.get(campo), f"{e.get('slug')}: campo obrigatorio ausente: {campo}"
        assert e['level'] in LEVELS, f"{e['slug']}: level invalido"
        for a in e.get('aliases', []):
            owner = canon.get(normalize_name(a))
            assert owner in (None, e['slug']), f"alias '{a}' colide com canonico de {owner}"


def test_cobertura_esperada_por_plano_real():
    """Numeros REAIS do catalogo oficial (espelho de producao). Ver docstring do modulo."""
    db = _session_with_catalog()
    plans = _plans()
    esperado = {
        '12': (9, 15),
        '19': (8, 19),
        '23': (10, 21),
        '24': (7, 11),
        '36': (12, 20),
        'SOTEL': (13, 28),
    }
    for k, (res, tot) in esperado.items():
        cov = build_enrichment(db, plans[k])['coverage']
        assert (cov['resolved'], cov['total']) == (res, tot), \
            f"plano {k}: cobertura {cov} != esperado {(res, tot)}"


def test_cobertura_total_consolidada():
    db = _session_with_catalog()
    plans = _plans()
    r = t = 0
    for k in plans:
        cov = build_enrichment(db, plans[k])['coverage']
        r += cov['resolved']; t += cov['total']
    assert (r, t) == (59, 114), f"cobertura consolidada {r}/{t} != 59/114"


def test_alias_resolve_variacao_conhecida():
    """Preserva a INTENCAO do teste antigo (resolucao por alias), com aliases que
    existem de fato no catalogo oficial. 'Puxador Frente'/'Pull Down' NAO estao no
    catalogo oficial nem em producao - o teste antigo dava confianca falsa."""
    db = _session_with_catalog()
    from services.exercise_resolver import build_index, resolve_with_index
    idx = build_index(db)
    for termo, slug in (('Extensora', 'cadeira-extensora'),
                        ('Serrote', 'remada-unilateral'),
                        ('Plank', 'prancha-frontal'),
                        ('Bench Press', 'supino-reto')):
        hit = resolve_with_index(idx, termo)
        assert hit and hit['slug'] == slug and hit['match'] == 'alias', \
            f"'{termo}' deveria resolver para {slug} por alias; obtido: {hit}"


def test_aliases_do_seed_obsoleto_ainda_nao_migrados():
    """Documenta (sem corrigir) as 12 chaves que existem no seed obsoleto e NAO no
    catalogo oficial. Decisao de incorporar e do Proprietario (nao inventar alias)."""
    db = _session_with_catalog()
    from services.exercise_resolver import build_index, resolve_with_index
    idx = build_index(db)
    nao_migrados = ['Puxador Frente', 'Pull Down', 'Puxada na Barra', 'Abdominal',
                    'Prancha Estatica', 'Desenvolvimento Militar']
    for termo in nao_migrados:
        assert resolve_with_index(idx, termo) is None, \
            f"'{termo}' passou a resolver: atualize este teste e o registro da decisao"
