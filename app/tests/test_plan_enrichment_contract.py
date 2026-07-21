"""
LIB-005 - contrato de colunas de enriquecimento + documentacao do drift ORM.

Decisao do Proprietario: NAO refatorar o ORM. As colunas de plano vivem no banco
via migrate.py e sao acessadas por SQL cru (padrao operacional atual). Este teste:
  (1) documenta o drift: o model ORM `ClientPlan` NAO declara `published_content`
      nem as colunas de enriquecimento;
  (2) prova o contrato de round-trip por SQL cru das colunas de enriquecimento,
      garantindo que `published_content` NAO e alterado pela escrita do enrichment.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text

from models.client_plan import ClientPlan


def test_drift_documentado_model_orm_nao_conhece_colunas_de_plano():
    cols = {c.name for c in ClientPlan.__table__.columns}
    # Drift real e conhecido: estas colunas existem no banco (migrate.py) mas NAO no ORM.
    assert 'published_content' not in cols
    assert 'enrichment_json' not in cols
    assert 'enrichment_source_hash' not in cols


def test_contrato_roundtrip_enrichment_sem_tocar_published_content():
    eng = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE client_plans ("
            "id INTEGER PRIMARY KEY, client_id INTEGER, content TEXT, "
            "published_content TEXT, enrichment_json TEXT, enrichment_source_hash TEXT, "
            "status TEXT, created_at TEXT)"
        ))
        c.execute(text(
            "INSERT INTO client_plans (id, client_id, content, published_content, status) "
            "VALUES (1, 12, 'rascunho', 'TREINO A\n1. Leg Press - 3x12', 'active')"
        ))

    published_antes = eng.connect().execute(
        text("SELECT published_content FROM client_plans WHERE id=1")).fetchone()[0]

    enrichment = {"exercises": [{"occurrence_key": "k", "name_raw": "Leg Press",
                                 "context_path": "Treino A", "library_ref": "leg-press",
                                 "status": "resolved", "match": "canonical"}],
                  "coverage": {"resolved": 1, "total": 1}}
    with eng.begin() as c:
        c.execute(
            text("UPDATE client_plans SET enrichment_json=:ej, enrichment_source_hash=:eh WHERE id=1"),
            {"ej": json.dumps(enrichment, ensure_ascii=False), "eh": "hash123"},
        )

    row = eng.connect().execute(text(
        "SELECT published_content, enrichment_json, enrichment_source_hash FROM client_plans WHERE id=1"
    )).fetchone()
    # published_content permanece EXATAMENTE o mesmo
    assert row[0] == published_antes
    # enriquecimento persistido e reidratavel
    assert json.loads(row[1]) == enrichment
    assert row[2] == "hash123"
