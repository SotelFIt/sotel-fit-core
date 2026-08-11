"""
LIB-006.1 - regressao: POST /admin/exercises DEVE persistir os aliases recebidos.

Bug corrigido: `create_exercise` construia `Exercise(...)` sem `aliases=`, entao a
criacao descartava o campo (PATCH ja funcionava via setattr generico). Este teste
prova a persistencia no CREATE via httpx.ASGITransport (in-process), sem producao,
sem token real, sem banco de producao (SQLite em memoria).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from core.security import require_admin
from models.exercise import Exercise
from models.exercise_substitution import ExerciseSubstitutionRule
from routers.exercise import admin_router

REG_ALIASES = ["Supino Inclinado com Barra", "Incline Bench Press", "Barbell Incline Bench Press"]


def _engine():
    eng = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    # LIB-013B: approved_substitutions virou projecao das regras, entao a tabela de
    # relacoes precisa existir mesmo num teste que so exercita `aliases`.
    Base.metadata.create_all(eng, tables=[Exercise.__table__,
                                          ExerciseSubstitutionRule.__table__])
    return eng


def _app(eng):
    app = FastAPI()
    app.include_router(admin_router)

    def _get_db_override():
        db = sessionmaker(bind=eng)()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_admin] = lambda: 0  # admin autenticado
    return app


def _post(app, body):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://t') as ac:
            return await ac.post('/admin/exercises', json=body)
    return asyncio.run(_run())


def _payload(**over):
    base = dict(
        slug='supino-inclinado', name='Supino Inclinado', aliases=list(REG_ALIASES),
        primary_muscle='peitoral', equipment='barra', level='avancado', is_active=True,
    )
    base.update(over)
    return base


def test_create_persiste_aliases_exatos_na_resposta_e_no_banco():
    eng = _engine()
    r = _post(_app(eng), _payload())
    assert r.status_code == 201, r.text
    # (3) resposta contem exatamente os tres aliases enviados
    assert r.json()['aliases'] == REG_ALIASES
    # (2) persistido no banco exatamente igual
    db = sessionmaker(bind=eng)()
    ex = db.query(Exercise).filter(Exercise.slug == 'supino-inclinado').first()
    assert ex is not None
    assert ex.aliases == REG_ALIASES


def test_create_lista_vazia_de_aliases_continua_funcionando():
    eng = _engine()
    r = _post(_app(eng), _payload(slug='leg-press', name='Leg Press', aliases=[],
                                  primary_muscle='quadriceps', equipment='maquina', level='iniciante'))
    assert r.status_code == 201, r.text
    assert r.json()['aliases'] == []


def test_create_omitindo_aliases_usa_default_vazio():
    eng = _engine()
    body = _payload(slug='crossover', name='Crossover', primary_muscle='peitoral',
                    equipment='cabo', level='intermediario')
    del body['aliases']
    r = _post(_app(eng), body)
    assert r.status_code == 201, r.text
    assert r.json()['aliases'] == []


def test_create_campos_existentes_permanecem_inalterados():
    eng = _engine()
    b = _post(_app(eng), _payload()).json()
    assert b['slug'] == 'supino-inclinado'
    assert b['name'] == 'Supino Inclinado'
    assert b['primary_muscle'] == 'peitoral'
    assert b['equipment'] == 'barra'
    assert b['level'] == 'avancado'
    assert b['is_active'] is True
