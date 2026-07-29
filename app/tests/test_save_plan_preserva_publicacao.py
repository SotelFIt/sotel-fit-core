"""
Regressao do bug save <-> publish (client_plans / client_diets).

Antes: save_client_plan/diet inativavam a linha publicada e criavam uma nova linha
active com published_content=NULL, "despublicando" o plano ate um novo release-plan.

Correcao: o save preserva na nova linha active o published_content (e o enriquecimento,
no caso do treino) da linha active anterior. release-plan continua sendo a UNICA acao
que substitui published_content pelo novo content.

Testes chamam as funcoes reais dos routers, com SQLite em memoria (NOW() registrado),
sem producao, sem token real, sem rede (Twilio neutralizado).
"""
import os
import sys

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("LANDBOT_SECRET_TOKEN", "test-token")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import routers.admin as admin_mod
from routers.admin import save_client_plan, save_client_diet, release_plan_by_id, SavePlanRequest, SaveDietRequest
from routers.clients import get_my_plan, get_my_diet
from services.client_safe import make_client_safe

_DDL = [
    "CREATE TABLE client_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, content TEXT, status TEXT, published_content TEXT, enrichment_json TEXT, enrichment_source_hash TEXT, created_at TEXT)",
    "CREATE TABLE client_diets (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, content TEXT, status TEXT, published_content TEXT, created_at TEXT)",
    "CREATE TABLE admin_audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, admin_id INTEGER, client_id INTEGER, details TEXT, created_at TEXT)",
    "CREATE TABLE clients (id INTEGER PRIMARY KEY, phone TEXT, status TEXT, name TEXT)",
    "CREATE TABLE conversation_states (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, status TEXT, step TEXT)",
    "CREATE TABLE whatsapp_events (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, message_sid TEXT, status TEXT, error_code TEXT, to_phone TEXT, context TEXT, created_at TEXT, updated_at TEXT)",
]

OLD = "2020-01-01 00:00:00"  # created_at fixo antigo garante que a nova linha (NOW()) e mais recente


def fresh_db():
    eng = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)

    @event.listens_for(eng, "connect")
    def _reg_now(dbapi_conn, _rec):
        dbapi_conn.create_function("NOW", 0, lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f"))

    db = sessionmaker(bind=eng)()
    for ddl in _DDL:
        db.execute(text(ddl))
    db.commit()
    return db


def _active_plan(db, cid=1):
    return db.execute(text(
        "SELECT content, published_content, enrichment_json, enrichment_source_hash "
        "FROM client_plans WHERE client_id=:c AND status='active' ORDER BY created_at DESC LIMIT 1"
    ), {"c": cid}).fetchone()


def _n_active(db, table, cid=1):
    return db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE client_id=:c AND status='active'"), {"c": cid}).scalar()


# 1) save preserva a publicacao anterior (content novo, published_content + enrichment mantidos)
def test_save_plan_preserva_publicacao_anterior():
    db = fresh_db()
    db.execute(text(
        "INSERT INTO client_plans (client_id, content, status, published_content, enrichment_json, enrichment_source_hash, created_at) "
        "VALUES (1,'PLANO A','active','PLANO A PUBLICADO',:enr,'hashA',:t)"
    ), {"enr": '{"coverage":{"resolved":1,"total":1}}', "t": OLD})
    db.commit()

    save_client_plan(1, SavePlanRequest(content="PLANO B"), db, 0)

    assert _n_active(db, "client_plans") == 1          # continua havendo uma unica linha ativa
    a = _active_plan(db)
    assert a[0] == "PLANO B"                            # novo rascunho salvo
    assert a[1] == "PLANO A PUBLICADO"                 # publicacao anterior PRESERVADA (nao despublica)
    assert a[2] is not None and "coverage" in a[2]     # enrichment_json preservado
    assert a[3] == "hashA"                             # enrichment_source_hash preservado


# 2) cliente continua lendo o plano publicado anterior apos um novo save
def test_cliente_le_publicacao_anterior_apos_save():
    db = fresh_db()
    db.execute(text(
        "INSERT INTO client_plans (client_id, content, status, published_content, created_at) "
        "VALUES (1,'PLANO A','active','PLANO A PUBLICADO',:t)"
    ), {"t": OLD})
    db.commit()

    save_client_plan(1, SavePlanRequest(content="PLANO B"), db, 0)

    out = get_my_plan(1, db, 0)
    assert out["content"] == "PLANO A PUBLICADO"       # cliente ainda ve A (nao B, nao vazio)


# 3) release substitui published_content pelo novo content (e continua sendo necessario)
def test_release_substitui_published_content(monkeypatch):
    db = fresh_db()
    db.execute(text("INSERT INTO clients (id, phone, status, name) VALUES (1,'+5511999998888','pending','Cliente Teste')"))
    db.execute(text(
        "INSERT INTO client_plans (client_id, content, status, published_content, created_at) "
        "VALUES (1,'TREINO B','active','TREINO A PUBLICADO',:t)"
    ), {"t": OLD})
    db.execute(text(
        "INSERT INTO client_diets (client_id, content, status, published_content, created_at) "
        "VALUES (1,'DIETA B','active','DIETA A PUBLICADA',:t)"
    ), {"t": OLD})
    db.commit()

    # antes do release: publicacao ainda e a anterior (prova de que save nao publicou)
    assert get_my_plan(1, db, 0)["content"] == "TREINO A PUBLICADO"

    # neutraliza Twilio (sem rede) — publicacao ja e commitada antes do envio de qualquer forma
    class _FakeMsg:
        sid = "SM_TEST"
        status = "queued"

    class _FakeTwilio:
        def __init__(self, *a, **k):
            pass

        class messages:
            @staticmethod
            def create(*a, **k):
                return _FakeMsg()

    monkeypatch.setattr(admin_mod, "TwilioClient", _FakeTwilio)

    release_plan_by_id(1, db, 0)

    pub = db.execute(text(
        "SELECT published_content FROM client_plans WHERE client_id=1 AND status='active' ORDER BY created_at DESC LIMIT 1"
    )).scalar()
    assert pub == make_client_safe("TREINO B")         # release publicou B
    assert get_my_plan(1, db, 0)["content"] == make_client_safe("TREINO B")


# 4) primeiro save sem publicacao previa continua retornando "em preparacao"
def test_primeiro_save_sem_publicacao_retorna_em_preparacao():
    db = fresh_db()
    save_client_plan(1, SavePlanRequest(content="PLANO B"), db, 0)   # nenhuma publicacao previa

    a = _active_plan(db)
    assert a[0] == "PLANO B"
    assert a[1] is None                                # published_content permanece NULL
    out = get_my_plan(1, db, 0)
    assert out["content"].startswith("Plano em prepara")   # "Plano em preparacao..."


# 5) equivalente para a DIETA (mesmo bug, mesma correcao)
def test_save_diet_preserva_publicacao_anterior():
    db = fresh_db()
    db.execute(text(
        "INSERT INTO client_diets (client_id, content, status, published_content, created_at) "
        "VALUES (1,'DIETA A','active','DIETA A PUBLICADA',:t)"
    ), {"t": OLD})
    db.commit()

    save_client_diet(1, SaveDietRequest(content="DIETA B"), db, 0)

    assert _n_active(db, "client_diets") == 1
    d = db.execute(text(
        "SELECT content, published_content FROM client_diets WHERE client_id=1 AND status='active' ORDER BY created_at DESC LIMIT 1"
    )).fetchone()
    assert d[0] == "DIETA B"                            # novo rascunho
    assert d[1] == "DIETA A PUBLICADA"                 # publicacao da dieta preservada
    assert get_my_diet(1, db, 0)["content"] == "DIETA A PUBLICADA"
