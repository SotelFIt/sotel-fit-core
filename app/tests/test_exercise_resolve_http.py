"""
LIB-005 Parte A - teste do CONTRATO HTTP de GET /exercises/resolve.

Valida o endpoint REAL (routers.exercise.public_router) via httpx.ASGITransport
(in-process), contornando a incompatibilidade pre-existente httpx 0.28 x
starlette TestClient. Prova: roteamento (/resolve nao e capturado por /{slug}),
autenticacao, retorno canonical/alias/sem-identidade, serializacao, inativo e
ausencia de matching aproximado.
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
from core.security import verify_dual_auth
from models.exercise import Exercise
from routers.exercise import public_router, admin_router


def _engine_seeded():
    eng = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(eng, tables=[Exercise.__table__])
    db = sessionmaker(bind=eng)()
    db.add_all([
        Exercise(slug='leg-press', name='Leg Press', aliases=[], primary_muscle='quadriceps',
                 equipment='maquina', level='iniciante', is_active=True),
        Exercise(slug='puxada-frontal', name='Puxada Frontal', aliases=['Puxador Frente', 'Pull Down'],
                 primary_muscle='costas', equipment='maquina', level='iniciante', is_active=True),
        Exercise(slug='stiff', name='Stiff', aliases=[], primary_muscle='posterior',
                 equipment='barra', level='intermediario', is_active=False),  # INATIVO
    ])
    db.commit()
    db.close()
    return eng


def _app(eng, *, authenticated=True):
    app = FastAPI()
    app.include_router(public_router)
    app.include_router(admin_router)

    def _get_db_override():
        db = sessionmaker(bind=eng)()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db_override
    if authenticated:
        app.dependency_overrides[verify_dual_auth] = lambda: 1  # cliente autenticado
    return app


def _get(app, path, **params):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://t') as ac:
            return await ac.get(path, params=params or None)
    return asyncio.run(_run())


def test_exige_autenticacao():
    # Sem override de auth e sem credenciais -> 401/403 (dependencia real ativa).
    app = _app(_engine_seeded(), authenticated=False)
    r = _get(app, '/exercises/resolve', name='Leg Press')
    assert r.status_code in (401, 403)


def test_resolve_nao_e_capturado_por_slug_e_retorna_canonical():
    r = _get(_app(_engine_seeded()), '/exercises/resolve', name='Leg press (se disponível)')
    assert r.status_code == 200
    body = r.json()
    # Se /{slug} tivesse capturado (slug='resolve'), viria 404. 200 {slug,match} prova o roteamento.
    assert body == {'slug': 'leg-press', 'match': 'canonical'}


def test_resolve_por_alias():
    r = _get(_app(_engine_seeded()), '/exercises/resolve', name='Puxador Frente')
    assert r.status_code == 200
    assert r.json() == {'slug': 'puxada-frontal', 'match': 'alias'}


def test_sem_identidade_retorna_404():
    r = _get(_app(_engine_seeded()), '/exercises/resolve', name='Exercicio Inexistente')
    assert r.status_code == 404


def test_inativo_nao_resolve():
    r = _get(_app(_engine_seeded()), '/exercises/resolve', name='Stiff')
    assert r.status_code == 404


def test_sem_matching_aproximado():
    # 'Leg' e substring de 'Leg Press', mas resolucao e por igualdade normalizada, nao LIKE.
    r = _get(_app(_engine_seeded()), '/exercises/resolve', name='Leg')
    assert r.status_code == 404


def test_serializacao_schema_do_retorno():
    r = _get(_app(_engine_seeded()), '/exercises/resolve', name='Pull Down')
    assert r.headers['content-type'].startswith('application/json')
    body = r.json()
    assert set(body.keys()) == {'slug', 'match'}
    assert body['slug'] == 'puxada-frontal'
    assert body['match'] in ('canonical', 'alias')
