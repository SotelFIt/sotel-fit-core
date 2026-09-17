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

  Antes (seed)    -> 12:11/15  19:9/19  23:10/21  24:11/11  36:15/20  SOTEL:13/28
  LIB-011B(oficial)-> 12:9/15   19:8/19  23:10/21  24:7/11   36:12/20  SOTEL:13/28  = 59/114 (52%)
  LIB-011C         -> 12:10/15  19:9/19  23:10/21  24:8/11   36:13/20  SOTEL:15/28  = 65/114 (57%)
  LIB-011D         -> 12:10/15  19:9/19  23:10/21  24:9/11   36:14/20  SOTEL:15/28  = 67/114 (59%)
  LIB-011E         -> 70/114 (61%)
  LIB-MEDIA(atual) -> 70/113 (62%) — o denominador caiu 1 porque a instrucao
                      'Descanso completo | Opcional: alongamento estatico' do
                      plano 19 deixou de ser tratada como exercicio.

  LIB-011E (2026-08-08): criou 3 canonicos PROPRIOS (supino-com-halteres,
  desenvolvimento-militar, rosca-direta-unilateral) apos auditoria de identidade.
  Ganho por NOVO CANONICO, nunca por alias forcado. FASE DE IDENTIDADE ENCERRADA.

  LIB-011D (2026-08-08): criou o canonico 'Remada Alta' (2 usos reais, sem
  equivalente na Biblioteca). Ganho por NOVO CANONICO, nao por alias.

  LIB-011C (2026-08-08): migrou 6 das 12 chaves historicas (as inequivocas e sem
  colisao) para o catalogo E para producao, subindo a cobertura de 52% para 57%.
  As 5 restantes ficaram AMBIGUAS (decisao do Proprietario) e 'Remada Alta' foi
  descartada por exigir criar exercicio novo.

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
        '12': (11, 15),
        # LIB-MEDIA: 19 -> 18. Uma ocorrencia do plano 19 era a instrucao
        # 'Descanso completo | Opcional: alongamento estatico 15', que passou
        # a ser classificada como ruido estrutural. Ela continua registrada no
        # enriquecimento; so deixou de contar como exercicio a catalogar.
        '19': (10, 18),
        '23': (10, 21),
        '24': (10, 11),
        '36': (14, 20),
        'SOTEL': (15, 28),
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
    # 114 -> 113 pelo mesmo motivo do plano 19: uma instrucao de descanso
    # deixou de ser contada como exercicio. O numerador nao muda.
    assert (r, t) == (70, 113), f"cobertura consolidada {r}/{t} != 70/113"


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
    # LIB-011C migrou as inequivocas; aqui ficam SO as classificadas AMBIGUAS,
    # que dependem de decisao do Proprietario (nao inventar alias).
    # LIB-011D: 'Supino com Haltere', 'Desenvolvimento Militar' e 'Rosca Direta
    # Unilateral' NAO viraram alias - sao CANDIDATOS A CANONICO PROPRIO (equipamento
    # e/ou padrao motor distintos). 'Puxada na Barra' e 'Abdominal' seguem genericas.
    # LIB-011E: 'Supino com Haltere', 'Desenvolvimento Militar' e 'Rosca Direta
    # Unilateral' viraram CANONICOS PROPRIOS (nao alias). Restam as 2 genericas,
    # que permanecem nao resolvidas POR DECISAO - nao por falta de trabalho.
    nao_migrados = ['Puxada na Barra', 'Abdominal']
    for termo in nao_migrados:
        assert resolve_with_index(idx, termo) is None, \
            f"'{termo}' passou a resolver: atualize este teste e o registro da decisao"
