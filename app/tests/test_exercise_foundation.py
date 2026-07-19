"""
LIB-002 - testes da fundacao da Biblioteca de Exercicios V1 (revisao pos-Codex).

Autoridade de schema (decisao do Proprietario 2026-07-17): a tabela nasce via
Base.metadata.create_all(); migrate.py guarda apenas o trigger PG de slug.

GARANTIAS E ONDE SAO PROVADAS:
- SQLite real (esta suite): defaults de listas, listas nao compartilhadas,
  CHECK de level no banco, unicidade do slug, imutabilidade ORM, timestamps.
- Compilacao/inspecao (esta suite): DDL PostgreSQL do model (defaults '[]',
  CHECK constraint), presenca e guarda de dialeto do trigger no migrate.py,
  tabelas de plano intactas, nenhum endpoint criado.
- PostgreSQL real (SOMENTE com TEST_POSTGRES_URL definida): rejeicao de
  bulk update do slug pelo trigger. Sem essa env var o teste e SKIPPED -
  SQLite NAO valida trigger plpgsql e esta suite nao finge que valida.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from core.database import Base
from models.exercise import Exercise
from schemas.exercise import ExerciseBase, ExerciseMedia, ExerciseResponse

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _engine():
    eng = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(eng, tables=[Exercise.__table__])
    return eng


def _session(eng=None):
    return sessionmaker(bind=eng or _engine())()


def _valid(**over):
    base = dict(slug='supino-reto', name='Supino reto', primary_muscle='Peito',
                equipment='Barra', level='iniciante')
    base.update(over)
    return Exercise(**base)


# ---------- defaults e listas ----------

def test_insert_sem_listas_retorna_listas_vazias_apos_leitura():
    db = _session()
    db.add(_valid())
    db.commit()
    db.expire_all()
    ex = db.query(Exercise).one()
    assert ex.secondary_muscles == []
    assert ex.common_errors == []
    assert ex.cautions == []
    assert ex.approved_substitutions == []
    assert ex.media == []
    assert ex.is_active is True
    assert ex.instructions is None


def test_listas_nao_sao_compartilhadas_entre_instancias():
    db = _session()
    db.add(_valid())
    db.add(_valid(slug='remada-curvada', name='Remada'))
    db.commit()
    db.expire_all()
    a = db.query(Exercise).filter_by(slug='supino-reto').one()
    b = db.query(Exercise).filter_by(slug='remada-curvada').one()
    a.secondary_muscles.append('Triceps')
    assert b.secondary_muscles == [], 'default mutavel vazou entre instancias'
    assert a.secondary_muscles is not b.secondary_muscles


def test_server_default_de_listas_no_banco():
    # INSERT cru sem as colunas de lista -> banco preenche '[]' (server_default)
    eng = _engine()
    with eng.begin() as conn:
        conn.execute(text(
            "INSERT INTO exercises (slug, name, primary_muscle, equipment, level) "
            "VALUES ('afundo', 'Afundo', 'Quadriceps', 'Peso corporal', 'iniciante')"
        ))
    db = _session(eng)
    ex = db.query(Exercise).filter_by(slug='afundo').one()
    assert ex.secondary_muscles == []
    assert ex.media == []
    assert ex.is_active is True


# ---------- constraints no banco ----------

def test_banco_rejeita_level_invalido():
    # INSERT cru (bypassa validacao Python) -> CHECK constraint do enum rejeita
    eng = _engine()
    with pytest.raises(IntegrityError):
        with eng.begin() as conn:
            conn.execute(text(
                "INSERT INTO exercises (slug, name, primary_muscle, equipment, level) "
                "VALUES ('x', 'X', 'Peito', 'Barra', 'mestre')"
            ))


def test_slug_duplicado_rejeitado():
    db = _session()
    db.add(_valid())
    db.commit()
    db.add(_valid(name='Outro nome'))
    with pytest.raises(IntegrityError):
        db.commit()


# ---------- imutabilidade do slug ----------

def test_atribuicao_comum_ao_slug_rejeitada():
    db = _session()
    db.add(_valid())
    db.commit()
    ex = db.query(Exercise).one()
    with pytest.raises(ValueError):
        ex.slug = 'outro-slug'


def test_reatribuir_mesmo_slug_permitido():
    db = _session()
    db.add(_valid())
    db.commit()
    ex = db.query(Exercise).one()
    ex.slug = 'supino-reto'
    db.commit()


# SQLSTATE do `RAISE EXCEPTION` sem ERRCODE explicito no plpgsql (raise_exception).
TRIGGER_SQLSTATE = 'P0001'
TRIGGER_MESSAGE = 'exercises.slug e imutavel'
TRIGGER_FUNCTION = 'exercises_slug_immutable'


@pytest.mark.skipif(
    not os.getenv('TEST_POSTGRES_URL'),
    reason='exige PostgreSQL real (defina TEST_POSTGRES_URL); SQLite nao valida trigger plpgsql',
)
def test_bulk_update_do_slug_rejeitado_no_postgres():
    """GARANTIA SO VERIFICAVEL EM POSTGRES REAL: o trigger exercises_slug_immutable
    rejeita bulk update (que bypassa o listener ORM).

    Exigencia da revisao Codex (LIB-002): um DBAPIError generico NAO conta como
    sucesso. A falha tem de vir comprovadamente do trigger de imutabilidade -
    provada pela funcao plpgsql `exercises_slug_immutable` na origem E pela
    mensagem 'exercises.slug e imutavel' OU pelo SQLSTATE P0001 configurado pelo
    trigger. Alem disso, o slug NAO pode ter mudado apos o bloqueio.
    """
    from migrate import run_migrations
    eng = create_engine(os.environ['TEST_POSTGRES_URL'])
    Base.metadata.create_all(eng, tables=[Exercise.__table__])
    run_migrations(eng)
    db = _session(eng)
    try:
        db.add(_valid(slug='pg-bulk-teste'))
        db.commit()

        with pytest.raises(DBAPIError) as exc_info:
            db.query(Exercise).filter_by(slug='pg-bulk-teste').update({'slug': 'mudou'})
            db.commit()
        db.rollback()

        # Excecao nativa do driver (psycopg2) por baixo do wrapper do SQLAlchemy.
        orig = exc_info.value.orig
        diag = getattr(orig, 'diag', None)
        sqlstate = (
            getattr(orig, 'pgcode', None)
            or getattr(diag, 'sqlstate', None)
        )
        primary = getattr(diag, 'message_primary', None) or ''
        context = getattr(diag, 'context', None) or ''
        full = f'{orig}\n{context}'  # str(orig) ja inclui o CONTEXT; reforca a checagem

        # (1) A falha veio DO TRIGGER de slug, nao de um erro qualquer do banco.
        assert TRIGGER_FUNCTION in full, (
            f'a falha nao foi originada pela funcao {TRIGGER_FUNCTION}; '
            f'erro real: {full!r}'
        )
        # (2) Mensagem esperada OU o SQLSTATE especifico do trigger.
        assert (TRIGGER_MESSAGE in primary or TRIGGER_MESSAGE in full) \
            or sqlstate == TRIGGER_SQLSTATE, (
            f"nem a mensagem '{TRIGGER_MESSAGE}' nem o SQLSTATE "
            f"{TRIGGER_SQLSTATE} presentes; sqlstate={sqlstate!r} erro={full!r}"
        )
        # (3) O bulk update foi efetivamente barrado: slug intacto.
        assert db.query(Exercise).filter_by(slug='pg-bulk-teste').count() == 1
        assert db.query(Exercise).filter_by(slug='mudou').count() == 0
    finally:
        db.rollback()
        with eng.begin() as conn:
            conn.execute(text("DELETE FROM exercises WHERE slug = 'pg-bulk-teste'"))


# ---------- verificacoes por compilacao/inspecao ----------

def test_ddl_postgres_compila_com_defaults_e_check():
    from sqlalchemy.dialects import postgresql
    ddl = str(CreateTable(Exercise.__table__).compile(dialect=postgresql.dialect()))
    assert "DEFAULT '[]'" in ddl, 'server_default de listas ausente no DDL PostgreSQL'
    assert 'CHECK' in ddl and 'iniciante' in ddl, 'CHECK constraint do level ausente no DDL'
    assert 'DEFAULT true' in ddl, 'server_default de is_active ausente no DDL PostgreSQL'


def test_trigger_pg_presente_e_guardado_no_migrate():
    src = open(os.path.join(APP_DIR, 'migrate.py'), encoding='utf-8').read()
    assert 'exercises_slug_immutable' in src, 'trigger de slug ausente do migrate.py'
    assert 'trg_exercises_slug_immutable' in src
    guard_pos = src.find('engine.dialect.name == "postgresql"')
    trigger_pos = src.find('exercises_slug_immutable')
    assert 0 <= guard_pos < trigger_pos, 'trigger PG sem guarda de dialeto antes dele'


def test_model_e_schema_possuem_timestamps():
    cols = {c.name for c in Exercise.__table__.columns}
    assert {'created_at', 'updated_at'} <= cols
    fields = set(ExerciseResponse.model_fields)
    assert {'created_at', 'updated_at'} <= fields


def test_tabelas_de_plano_intactas():
    from models.plan import Plan
    from models.client_plan import ClientPlan
    assert {c.name for c in Plan.__table__.columns} == {
        'id', 'client_id', 'onboarding_id', 'training_plan', 'diet_plan',
        'notes', 'created_at', 'updated_at',
    }
    assert {c.name for c in ClientPlan.__table__.columns} == {
        'id', 'client_id', 'content', 'status', 'created_at',
    }


def test_endpoints_de_exercicio_registrados_lib003():
    """LIB-002 nasceu SEM endpoints (guard original). A LIB-003 adiciona a API da
    biblioteca; este teste passou a afirmar o oposto: o router de exercicios existe
    e esta registrado em main.py. Historico do guard preservado no git."""
    router_path = os.path.join(APP_DIR, 'routers', 'exercise.py')
    assert os.path.exists(router_path), 'routers/exercise.py (LIB-003) ausente'
    router_src = open(router_path, encoding='utf-8').read()
    assert '/exercises' in router_src.replace('prefix="/exercises"', '/exercises')
    main_src = open(os.path.join(APP_DIR, 'main.py'), encoding='utf-8', errors='ignore').read()
    assert 'from routers.exercise import' in main_src, 'router de exercises nao registrado em main.py'


# ---------- schemas de dominio ----------

def test_schema_valida_payload_completo():
    e = ExerciseBase(
        slug='agachamento-livre', name='Agachamento livre', primary_muscle='Quadriceps',
        secondary_muscles=['Gluteos'], equipment='Barra', level='intermediario',
        instructions='Desca controlado.', common_errors=['Joelho para dentro'],
        cautions=['Hernia lombar'], approved_substitutions=['leg-press'],
        media=[{'type': 'video', 'url': 'https://x/y.mp4'}],
    )
    assert e.media[0].alt is None
    assert e.is_active is True


def test_schema_defaults_vazios_e_nao_compartilhados():
    e1 = ExerciseBase(slug='remada', name='Remada', primary_muscle='Costas',
                      equipment='Halter', level='avancado')
    e2 = ExerciseBase(slug='barra-fixa', name='Barra fixa', primary_muscle='Costas',
                      equipment='Barra', level='avancado')
    e1.secondary_muscles.append('Biceps')
    assert e2.secondary_muscles == []


def test_schema_rejeita_level_invalido():
    with pytest.raises(ValidationError):
        ExerciseBase(slug='x', name='X', primary_muscle='Peito', equipment='Barra', level='expert')


def test_schema_rejeita_media_sem_url():
    with pytest.raises(ValidationError):
        ExerciseMedia(type='video')
