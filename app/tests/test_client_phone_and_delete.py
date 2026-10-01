"""
Troca de telefone e exclusao logica do aluno.

Duas operacoes que mexem em IDENTIDADE, nao em cadastro:

  - trocar o telefone move junto a conversa de WhatsApp e o onboarding. Se
    ficassem para tras, a proxima mensagem do numero antigo criaria um cliente
    novo e o aluno sumiria do proprio historico;

  - excluir e LOGICO: sai da lista e perde acesso, mas nada e apagado. Precisa
    derrubar sessao ja aberta e nao pode ser desfeito sozinho por pagamento,
    WhatsApp ou onboarding.

O override de `get_db` e aplicado por TESTE e restaurado no fim. Seis modulos
sobrescrevem essa dependencia no import e o ultimo importado ganha; aplicar no
import faria estes testes passarem isolados e cairem na suite completa.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault("JWT_SECRET_KEY", "ec/hBUFhntuNSkRbbVvo6CnWDOkXV2b8TMLI5vMcFd8=")
os.environ.setdefault("LANDBOT_SECRET_TOKEN", "token-admin-teste")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import get_db
from core.security import create_access_token
from main import app

ADMIN = {"x-api-key": os.environ["LANDBOT_SECRET_TOKEN"]}
ANA = {"Authorization": f"Bearer {create_access_token(1)}"}

ANTIGO = "+5517991110001"
NOVO_BRUTO = "(17) 99222-0002"
NOVO = "+5517992220002"

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app, raise_server_exceptions=False)

ESQUEMA = (
    """CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT, objective TEXT,
        difficulty TEXT, status TEXT, age INTEGER, weight REAL, height REAL,
        goal TEXT, deleted_at TIMESTAMP, created_at TIMESTAMP, updated_at TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS conversation_states (
        id INTEGER PRIMARY KEY, phone TEXT UNIQUE NOT NULL, step TEXT, status TEXT)""",
    """CREATE TABLE IF NOT EXISTS lead_onboardings (
        id INTEGER PRIMARY KEY, phone TEXT, respostas TEXT, created_at TIMESTAMP)""",
    # Historico: existe para provar que NAO e reescrito.
    """CREATE TABLE IF NOT EXISTS whatsapp_events (
        id INTEGER PRIMARY KEY, to_phone TEXT, status TEXT)""",
    """CREATE TABLE IF NOT EXISTS client_plans (
        id INTEGER PRIMARY KEY, client_id INTEGER, published_content TEXT, status TEXT,
        created_at TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS client_checkins (
        id INTEGER PRIMARY KEY, client_id INTEGER, peso REAL, created_at TIMESTAMP)""",
)


@pytest.fixture(autouse=True)
def _base():
    anterior = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db
    with engine.begin() as c:
        for ddl in ESQUEMA:
            c.exec_driver_sql(ddl)
        for t in ("clients", "conversation_states", "lead_onboardings",
                  "whatsapp_events", "client_plans", "client_checkins"):
            c.exec_driver_sql(f"DELETE FROM {t}")
        c.exec_driver_sql(
            "INSERT INTO clients (id,name,email,phone,objective,difficulty,status,"
            "age,weight,height,goal,deleted_at,created_at) VALUES"
            f" (1,'Ana','ana@exemplo.invalid','{ANTIGO}','Emagrecer','inter','active',"
            "30,62.5,1.65,'anamnese',NULL,CURRENT_TIMESTAMP),"
            " (2,'Bruno','bruno@exemplo.invalid','+5517993330003','Hipertrofia','ini',"
            "'active',41,88.0,1.8,'outra',NULL,CURRENT_TIMESTAMP)"
        )
        c.exec_driver_sql(
            f"INSERT INTO conversation_states (phone,step,status) VALUES ('{ANTIGO}','ativo','active')")
        c.exec_driver_sql(
            f"INSERT INTO lead_onboardings (phone,respostas) VALUES ('{ANTIGO}','r1'),"
            f" ('whatsapp:{ANTIGO}','r2'), ('{ANTIGO.lstrip('+')}','r3')")
        c.exec_driver_sql(
            f"INSERT INTO whatsapp_events (to_phone,status) VALUES ('{ANTIGO}','delivered')")
        c.exec_driver_sql(
            "INSERT INTO client_plans (client_id,published_content,status) VALUES (1,'TREINO A','active')")
        c.exec_driver_sql("INSERT INTO client_checkins (client_id,peso) VALUES (1,62.0)")
    try:
        yield
    finally:
        if anterior is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = anterior


def _uma(sql):
    with engine.begin() as c:
        return c.exec_driver_sql(sql).fetchone()


def _conta(sql):
    return _uma(sql)[0]


# ========================================================= TROCA DE TELEFONE

def test_admin_troca_o_telefone_e_normaliza():
    r = client.patch("/clients/1", json={"phone": NOVO_BRUTO}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == NOVO, "o numero precisa ser gravado em E.164"
    assert r.json()["id"] == 1, "o id do cliente nao pode mudar"


def test_a_conversa_de_whatsapp_vai_junto():
    """Sem isto, a proxima mensagem do numero novo abriria conversa do zero."""
    client.patch("/clients/1", json={"phone": NOVO_BRUTO}, headers=ADMIN)
    assert _conta(f"SELECT count(*) FROM conversation_states WHERE phone='{NOVO}'") == 1
    assert _conta(f"SELECT count(*) FROM conversation_states WHERE phone='{ANTIGO}'") == 0


def test_o_onboarding_vai_junto_em_todas_as_variantes():
    """O numero foi gravado de tres jeitos ao longo do tempo; os tres migram."""
    client.patch("/clients/1", json={"phone": NOVO_BRUTO}, headers=ADMIN)
    assert _conta(f"SELECT count(*) FROM lead_onboardings WHERE phone='{NOVO}'") == 3
    assert _conta("SELECT count(*) FROM lead_onboardings WHERE phone LIKE '%1110001%'") == 0


def test_historico_NAO_e_reescrito():
    """`whatsapp_events` registra o que foi enviado NAQUELE dia, para aquele
    numero. Reescrever seria falsificar o historico."""
    client.patch("/clients/1", json={"phone": NOVO_BRUTO}, headers=ADMIN)
    assert _conta(f"SELECT count(*) FROM whatsapp_events WHERE to_phone='{ANTIGO}'") == 1


def test_o_resto_do_cadastro_fica_intacto():
    client.patch("/clients/1", json={"phone": NOVO_BRUTO}, headers=ADMIN)
    linha = _uma("SELECT name,email,objective,difficulty,status,age,weight,height,goal"
                 " FROM clients WHERE id=1")
    assert linha == ("Ana", "ana@exemplo.invalid", "Emagrecer", "inter", "active",
                     30, 62.5, 1.65, "anamnese")


def test_telefone_invalido_e_recusado_sem_gravar_nada():
    antes = _uma("SELECT phone,name FROM clients WHERE id=1")
    r = client.patch("/clients/1", json={"phone": "abc", "name": "Nome Novo"}, headers=ADMIN)
    assert r.status_code == 422
    assert _uma("SELECT phone,name FROM clients WHERE id=1") == antes


def test_telefone_de_outro_cliente_e_recusado():
    antes = _uma("SELECT phone,name FROM clients WHERE id=1")
    r = client.patch("/clients/1", json={"phone": "+5517993330003"}, headers=ADMIN)
    assert r.status_code == 409
    assert "2" in r.json()["detail"]
    assert _uma("SELECT phone,name FROM clients WHERE id=1") == antes


def test_nao_absorve_conversa_de_outra_pessoa():
    """`conversation_states.phone` e UNIQUE. Se ja ha conversa no numero de
    destino, ela e de outra pessoa — juntar as duas e o pior resultado possivel."""
    with engine.begin() as c:
        c.exec_driver_sql(
            f"INSERT INTO conversation_states (phone,step,status) VALUES ('{NOVO}','ativo','active')")
    antes = _uma("SELECT phone FROM clients WHERE id=1")
    r = client.patch("/clients/1", json={"phone": NOVO_BRUTO}, headers=ADMIN)
    assert r.status_code == 409
    assert _uma("SELECT phone FROM clients WHERE id=1") == antes
    assert _conta(f"SELECT count(*) FROM conversation_states WHERE phone='{ANTIGO}'") == 1


def test_ROLLBACK_completo_quando_o_telefone_falha():
    """O nome vai no mesmo payload. Se o telefone e recusado, o nome tambem nao
    entra — tudo-ou-nada na mesma transacao."""
    r = client.patch("/clients/1",
                     json={"name": "NAO PODE GRAVAR", "phone": "+5517993330003"},
                     headers=ADMIN)
    assert r.status_code == 409
    assert _uma("SELECT name FROM clients WHERE id=1")[0] == "Ana"


def test_trocar_para_o_mesmo_numero_nao_quebra():
    r = client.patch("/clients/1", json={"phone": ANTIGO}, headers=ADMIN)
    assert r.status_code == 200
    assert _conta(f"SELECT count(*) FROM conversation_states WHERE phone='{ANTIGO}'") == 1


def test_telefone_e_nome_juntos_quando_tudo_e_valido():
    r = client.patch("/clients/1", json={"name": "Ana Nova", "phone": NOVO_BRUTO},
                     headers=ADMIN)
    assert r.status_code == 200
    assert _uma("SELECT name,phone FROM clients WHERE id=1") == ("Ana Nova", NOVO)


def test_somente_admin_troca_telefone():
    r = client.patch("/clients/1", json={"phone": NOVO_BRUTO}, headers=ANA)
    assert r.status_code == 403
    assert _uma("SELECT phone FROM clients WHERE id=1")[0] == ANTIGO


# ============================================================ EXCLUSAO LOGICA

def test_admin_exclui_e_o_cadastro_continua_no_banco():
    r = client.delete("/clients/1", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] is True
    assert _conta("SELECT count(*) FROM clients WHERE id=1") == 1, "nada e apagado"
    assert _uma("SELECT deleted_at FROM clients WHERE id=1")[0] is not None


def test_exclusao_NAO_mexe_em_status():
    """`status` fala de assinatura/suspensao. Confundir os dois tornaria
    impossivel saber quem foi removido e quem so esta com a assinatura parada."""
    client.delete("/clients/1", headers=ADMIN)
    assert _uma("SELECT status FROM clients WHERE id=1")[0] == "active"


def test_historico_do_aluno_e_preservado():
    client.delete("/clients/1", headers=ADMIN)
    assert _conta("SELECT count(*) FROM client_plans WHERE client_id=1") == 1
    assert _conta("SELECT count(*) FROM client_checkins WHERE client_id=1") == 1
    assert _conta("SELECT count(*) FROM lead_onboardings WHERE phone LIKE '%1110001%'") == 3


def test_sai_da_listagem():
    antes = len(client.get("/clients", headers=ADMIN).json())
    client.delete("/clients/1", headers=ADMIN)
    depois = client.get("/clients", headers=ADMIN).json()
    assert len(depois) == antes - 1
    assert all(c["id"] != 1 for c in depois)


def test_detalhe_responde_404_como_se_nao_existisse():
    client.delete("/clients/1", headers=ADMIN)
    assert client.get("/clients/1", headers=ADMIN).status_code == 404


def test_login_bloqueado():
    client.delete("/clients/1", headers=ADMIN)
    r = client.post("/auth/login", json={"email": "ana@exemplo.invalid"})
    assert r.status_code == 404


def test_sessao_JA_ABERTA_perde_acesso():
    """O token continua com assinatura valida: o que mudou foi o cadastro.
    Sem esta checagem, quem ja estava logado seguiria usando o app."""
    assert client.get("/clients/1/plan", headers=ANA).status_code == 200
    client.delete("/clients/1", headers=ADMIN)
    assert client.get("/clients/1/plan", headers=ANA).status_code == 401
    assert client.post("/auth/verify", headers=ANA).status_code == 401


def test_pagamento_e_whatsapp_NAO_reativam():
    """`get_or_create_client_from_phone` e a porta de entrada desses fluxos."""
    from services.client_service import ClienteExcluido, get_or_create_client_from_phone

    client.delete("/clients/1", headers=ADMIN)
    db = TestingSessionLocal()
    try:
        with pytest.raises(ClienteExcluido):
            get_or_create_client_from_phone(db, ANTIGO, name="Ana")
    finally:
        db.close()
    assert _conta("SELECT count(*) FROM clients WHERE phone = :p".replace(":p", f"'{ANTIGO}'")) == 1


def test_excluir_duas_vezes_nao_e_erro():
    client.delete("/clients/1", headers=ADMIN)
    primeira = _uma("SELECT deleted_at FROM clients WHERE id=1")[0]
    r = client.delete("/clients/1", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["ja_estava_excluido"] is True
    assert _uma("SELECT deleted_at FROM clients WHERE id=1")[0] == primeira


def test_somente_admin_exclui():
    r = client.delete("/clients/1", headers=ANA)
    assert r.status_code == 403
    assert _uma("SELECT deleted_at FROM clients WHERE id=1")[0] is None


def test_cliente_inexistente_404():
    assert client.delete("/clients/9999", headers=ADMIN).status_code == 404


def test_excluido_nao_pode_ser_editado():
    client.delete("/clients/1", headers=ADMIN)
    assert client.patch("/clients/1", json={"name": "X"}, headers=ADMIN).status_code == 404
