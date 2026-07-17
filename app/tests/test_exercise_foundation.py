"""
LIB-002 - testes da fundacao da Biblioteca de Exercicios V1.
Cobre: criacao do model, defaults, unicidade do slug, imutabilidade do slug,
enum de nivel, schemas de dominio e migration 002 (upgrade + downgrade)
em ambiente descartavel.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.exercise import Exercise
from schemas.exercise import ExerciseBase, ExerciseMedia


def _session():
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine, tables=[Exercise.__table__])
    return sessionmaker(bind=engine)()


def _valid(**over):
    base = dict(slug='supino-reto', name='Supino reto', primary_muscle='Peito',
                equipment='Barra', level='iniciante')
    base.update(over)
    return Exercise(**base)


# ---------- model + defaults ----------

def test_cria_exercicio_com_defaults():
    db = _session()
    db.add(_valid())
    db.commit()
    ex = db.query(Exercise).one()
    assert ex.id == 1
    assert ex.slug == 'supino-reto'
    assert ex.secondary_muscles == []
    assert ex.common_errors == []
    assert ex.cautions == []
    assert ex.approved_substitutions == []
    assert ex.media == []
    assert ex.is_active is True
    assert ex.instructions is None
    assert ex.created_at is not None
    assert ex.updated_at is not None


def test_slug_unico():
    db = _session()
    db.add(_valid())
    db.commit()
    db.add(_valid(name='Outro nome'))
    with pytest.raises(IntegrityError):
        db.commit()


def test_slug_imutavel():
    db = _session()
    db.add(_valid())
    db.commit()
    ex = db.query(Exercise).one()
    with pytest.raises(ValueError):
        ex.slug = 'outro-slug'


def test_slug_reatribuir_mesmo_valor_nao_falha():
    db = _session()
    db.add(_valid())
    db.commit()
    ex = db.query(Exercise).one()
    ex.slug = 'supino-reto'  # mesmo valor: permitido
    db.commit()


def test_level_enum_rejeita_valor_invalido():
    db = _session()
    db.add(_valid(level='mestre'))
    with pytest.raises((StatementError, LookupError)):
        db.commit()


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


def test_schema_defaults_vazios():
    e = ExerciseBase(slug='remada', name='Remada', primary_muscle='Costas',
                     equipment='Halter', level='avancado')
    assert e.secondary_muscles == []
    assert e.common_errors == []
    assert e.cautions == []
    assert e.approved_substitutions == []
    assert e.media == []


def test_schema_rejeita_level_invalido():
    with pytest.raises(ValidationError):
        ExerciseBase(slug='x', name='X', primary_muscle='Peito', equipment='Barra', level='expert')


def test_schema_rejeita_media_sem_url():
    with pytest.raises(ValidationError):
        ExerciseMedia(type='video')


def test_schema_rejeita_obrigatorios_vazios():
    with pytest.raises(ValidationError):
        ExerciseBase(slug='', name='X', primary_muscle='Peito', equipment='Barra', level='iniciante')


# ---------- migration 002 (ambiente descartavel) ----------

def test_migration_upgrade_e_downgrade(tmp_path):
    from alembic import command
    from alembic.config import Config

    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    db_path = tmp_path / 'disposable.db'
    url = f'sqlite:///{db_path.as_posix()}'

    cfg = Config(os.path.join(app_dir, 'alembic.ini'))
    cfg.set_main_option('script_location', os.path.join(app_dir, 'alembic'))
    cfg.set_main_option('sqlalchemy.url', url)

    # banco descartavel comeca no estado da 001 (sem tocar tabelas existentes)
    command.stamp(cfg, '001_add_landbot_user_id')

    command.upgrade(cfg, 'head')
    insp = inspect(create_engine(url))
    assert 'exercises' in insp.get_table_names()
    cols = {c['name'] for c in insp.get_columns('exercises')}
    assert {'id', 'slug', 'name', 'primary_muscle', 'secondary_muscles', 'equipment',
            'level', 'instructions', 'common_errors', 'cautions',
            'approved_substitutions', 'media', 'is_active',
            'created_at', 'updated_at'} <= cols
    uniques = [i for i in insp.get_indexes('exercises') if i['unique']]
    assert any('slug' in i['column_names'] for i in uniques)

    command.downgrade(cfg, '001_add_landbot_user_id')
    insp2 = inspect(create_engine(url))
    assert 'exercises' not in insp2.get_table_names()
