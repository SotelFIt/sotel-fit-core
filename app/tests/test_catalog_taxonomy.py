"""
LIB-011A - identidade e taxonomia do catalogo OFICIAL da Biblioteca.

Trava, sobre `app/data/exercise_catalog_sprint1.json` (fonte oficial):
  - vocabulario controlado de primary_muscle / equipment / level;
  - unicidade de slug e de nome canonico (bruto e NORMALIZADO);
  - ausencia de colisao sob normalize_name entre nome e aliases, dentro e entre exercicios;
  - schema valido (ExerciseCreate).

Regra do vocabulario: singular e plural NAO coexistem (ex.: 'halteres', nunca 'halter').
Valor novo so entra no catalogo apos decisao do Proprietario -> este teste falha antes.

NAO cobre conteudo tecnico (instrucoes/midia/substituicoes) - fora do escopo da LIB-011.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from schemas.exercise import ExerciseCreate
from services.exercise_resolver import normalize_name

CATALOG = os.path.join(os.path.dirname(__file__), '..', 'data', 'exercise_catalog_sprint1.json')

# Vocabulario controlado - derivado dos dados REAIS (nenhum valor inventado).
PRIMARY_MUSCLE = {
    'peitoral', 'costas', 'ombros', 'biceps', 'triceps',
    'quadriceps', 'posteriores', 'gluteos', 'panturrilhas', 'core',
}
EQUIPMENT = {'peso corporal', 'barra', 'halteres', 'maquina', 'cabo'}
LEVEL = {'iniciante', 'intermediario', 'avancado'}


def _catalog():
    with open(CATALOG, encoding='utf-8') as f:
        return json.load(f)['exercises']


def test_schema_valido_para_todos():
    for e in _catalog():
        ExerciseCreate(**e)  # levanta se invalido


def test_primary_muscle_no_vocabulario_controlado():
    fora = sorted({e['primary_muscle'] for e in _catalog()} - PRIMARY_MUSCLE)
    assert not fora, f"primary_muscle fora do vocabulario controlado: {fora}"


def test_equipment_no_vocabulario_controlado():
    fora = sorted({e['equipment'] for e in _catalog()} - EQUIPMENT)
    assert not fora, f"equipment fora do vocabulario controlado: {fora}"


def test_equipment_nao_mistura_singular_e_plural():
    vals = {e['equipment'] for e in _catalog()}
    assert 'halter' not in vals, "use 'halteres' (plural); 'halter' e variante proibida"


def test_level_no_vocabulario_controlado():
    fora = sorted({e['level'] for e in _catalog()} - LEVEL)
    assert not fora, f"level fora do vocabulario controlado: {fora}"


def test_slug_unico():
    slugs = [e['slug'] for e in _catalog()]
    dup = [s for s, c in collections.Counter(slugs).items() if c > 1]
    assert not dup, f"slug duplicado: {dup}"


def test_nome_canonico_unico_bruto_e_normalizado():
    nomes = [e['name'] for e in _catalog()]
    dup = [s for s, c in collections.Counter(nomes).items() if c > 1]
    assert not dup, f"nome canonico duplicado: {dup}"
    norm = [normalize_name(n) for n in nomes]
    dupn = [s for s, c in collections.Counter(norm).items() if c > 1]
    assert not dupn, f"nome canonico duplicado sob normalize_name: {dupn}"


def test_sem_alias_duplicado_dentro_do_mesmo_exercicio():
    for e in _catalog():
        na = [normalize_name(a) for a in (e.get('aliases') or [])]
        dup = [a for a, c in collections.Counter(na).items() if c > 1 and a]
        assert not dup, f"{e['slug']}: alias duplicado sob normalizacao: {dup}"


def test_alias_nao_repete_o_proprio_nome_canonico():
    for e in _catalog():
        na = {normalize_name(a) for a in (e.get('aliases') or [])}
        assert normalize_name(e['name']) not in na, f"{e['slug']}: alias igual ao nome canonico"


def test_sem_colisao_de_normalizacao_entre_exercicios_distintos():
    """Chave normalizada (nome ou alias) nunca pode apontar para dois slugs."""
    index = {}
    colisoes = []
    for e in _catalog():   # canonicos primeiro (mesma precedencia do build_index)
        k = normalize_name(e['name'])
        if k and k not in index:
            index[k] = e['slug']
    for e in _catalog():
        for a in (e.get('aliases') or []):
            k = normalize_name(a)
            if not k:
                continue
            if k in index and index[k] != e['slug']:
                colisoes.append((k, index[k], e['slug']))
            else:
                index.setdefault(k, e['slug'])
    assert not colisoes, f"colisao de normalizacao entre exercicios distintos: {colisoes}"


def test_campos_obrigatorios_presentes():
    for e in _catalog():
        for campo in ('slug', 'name', 'primary_muscle', 'equipment', 'level'):
            assert e.get(campo), f"{e.get('slug')}: campo obrigatorio ausente: {campo}"


def test_quantidade_do_catalogo_oficial():
    cat = _catalog()
    assert len(cat) == 30, f"catalogo oficial deve ter 30 exercicios (25 Sprint 1 + 4 na LIB-011B + Remada Alta na LIB-011D); tem {len(cat)}"

