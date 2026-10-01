"""
Edicao do cadastro do cliente pelo painel - PATCH /clients/{client_id}.

A rota existia e nunca teve teste. Ela sustenta o botao "Editar dados" do
Admin, e tres garantias dela nao sao obvias olhando o codigo:

  1. e PARCIAL: o que nao vem no payload nao e tocado. A anamnese nem sequer
     mora nesta tabela (`lead_onboardings`/`onboarding`), entao nao ha como
     esta rota apaga-la;
  2. `phone` e recusado - telefone e identidade (BL-PHONE-001) e e por ele que
     o WhatsApp, o onboarding e a ativacao de lead encontram o cliente;
  3. e-mail duplicado e recusado - `/auth/login` casa por e-mail e pega o
     PRIMEIRO resultado, e a coluna nao tem unique.

Isolamento igual ao de test_exercise_api.py: SQLite in-memory com override de
get_db no app REAL.
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

from core.database import Base, get_db
from core.security import create_access_token
from models.client import Client  # noqa: F401  (registra a tabela no metadata)
from main import app

ADMIN = {"x-api-key": os.environ["LANDBOT_SECRET_TOKEN"]}
CLIENTE_1 = {"Authorization": f"Bearer {create_access_token(1)}"}

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

CAMPOS = ("name", "email", "phone", "objective", "difficulty", "status",
          "age", "weight", "height", "goal")


@pytest.fixture(autouse=True)
def _base_limpa():
    # O override do get_db e aplicado AQUI, nao no import.
    #
    # `app` e global e seis modulos de teste sobrescrevem `get_db` no momento
    # do import: o ultimo importado ganha, e todos os outros passam a rodar
    # contra a engine alheia. Isolado o modulo passava; na suite completa,
    # nove destes testes caiam com erro de SQLite — procurando a tabela
    # `clients` numa base que nao e a desta suite.
    #
    # Aplicar por TESTE e restaurar no fim resolve na causa: a ordem de import
    # deixa de importar e nenhum outro modulo e afetado.
    anterior = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db

    Base.metadata.create_all(engine, tables=[Client.__table__])
    with engine.begin() as conn:
        # `updated_at` nao esta no modelo ORM: em producao ele e criado pelo
        # migrate.py. Reproduzido aqui para o teste exercitar o MESMO UPDATE.
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(clients)")]
        if "updated_at" not in cols:
            conn.exec_driver_sql("ALTER TABLE clients ADD COLUMN updated_at TIMESTAMP")
        conn.exec_driver_sql("DELETE FROM clients")
        conn.exec_driver_sql(
            "INSERT INTO clients (id, name, email, phone, objective, difficulty,"
            " status, age, weight, height, goal, created_at) VALUES"
            " (1,'Ana Original','ana@exemplo.invalid','+5511999990001','Emagrecer',"
            "'intermediario','active',30,62.5,1.65,'meta antiga',CURRENT_TIMESTAMP),"
            " (2,'Bruno Outro','bruno@exemplo.invalid','+5511999990002','Hipertrofia',"
            "'iniciante','active',41,88.0,1.80,'outra meta',CURRENT_TIMESTAMP)"
        )
    try:
        yield
    finally:
        if anterior is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = anterior


def _ler(cid=1):
    with engine.begin() as conn:
        linha = conn.exec_driver_sql(
            "SELECT name, email, phone, objective, difficulty, status, age,"
            " weight, height, goal FROM clients WHERE id = " + str(int(cid))
        ).fetchone()
    return dict(zip(CAMPOS, linha))


# ------------------------------------------------------------------ gravacao

def test_admin_edita_e_o_dado_persiste():
    r = client.patch("/clients/1", json={"name": "Ana Corrigida"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Ana Corrigida"
    assert _ler()["name"] == "Ana Corrigida", "respondeu 200 mas nao gravou"


def test_edicao_e_PARCIAL_o_resto_fica_intacto():
    """O risco real do formulario: mandar meia duzia de campos e zerar o resto."""
    antes = _ler()
    r = client.patch("/clients/1", json={"objective": "Manutencao"}, headers=ADMIN)
    assert r.status_code == 200
    depois = _ler()
    assert depois["objective"] == "Manutencao"
    for campo in CAMPOS:
        if campo == "objective":
            continue
        assert depois[campo] == antes[campo], f"{campo} mudou sem ter sido enviado"


def test_varios_campos_de_uma_vez():
    r = client.patch(
        "/clients/1",
        json={"name": "Ana", "age": 31, "weight": 61.0, "height": 1.66,
              "objective": "Forca"},
        headers=ADMIN,
    )
    assert r.status_code == 200
    d = _ler()
    assert (d["name"], d["age"], d["weight"], d["height"], d["objective"]) == (
        "Ana", 31, 61.0, 1.66, "Forca")
    assert d["phone"] == "+5511999990001", "telefone nao muda por tabela"


# ------------------------------------------------------------------ telefone

def test_telefone_e_recusado_e_nada_e_gravado():
    """BL-PHONE-001: telefone e identidade. WhatsApp, onboarding e ativacao de
    lead encontram o cliente por ele."""
    antes = _ler()
    r = client.patch(
        "/clients/1",
        json={"name": "Nome Novo", "phone": "+5511900000000"},
        headers=ADMIN,
    )
    assert r.status_code == 422
    assert _ler() == antes, "recusou o telefone mas gravou o resto do payload"


# -------------------------------------------------------------- e-mail unico

def test_email_de_outro_cliente_e_recusado():
    """`/auth/login` casa por e-mail e pega o PRIMEIRO resultado; a coluna nao
    tem unique. Duplicar e-mail e entregar a conta errada a alguem."""
    antes = _ler()
    r = client.patch("/clients/1", json={"email": "bruno@exemplo.invalid"},
                     headers=ADMIN)
    assert r.status_code == 409
    assert "2" in r.json()["detail"], "a mensagem precisa dizer de quem e o e-mail"
    assert _ler() == antes, "recusou e mesmo assim gravou"


def test_duplicidade_ignora_caixa_e_espacos():
    r = client.patch("/clients/1", json={"email": "  BRUNO@Exemplo.INVALID  "},
                     headers=ADMIN)
    assert r.status_code == 409


def test_manter_o_proprio_email_continua_valendo():
    r = client.patch("/clients/1",
                     json={"email": "ana@exemplo.invalid", "age": 33}, headers=ADMIN)
    assert r.status_code == 200
    assert _ler()["age"] == 33


def test_email_novo_e_aceito_sem_espacos_em_volta():
    r = client.patch("/clients/1", json={"email": "  ana.nova@exemplo.invalid "},
                     headers=ADMIN)
    assert r.status_code == 200
    assert _ler()["email"] == "ana.nova@exemplo.invalid", "espaco em volta quebra o login"


# -------------------------------------------------------------------- acesso

def test_somente_admin_edita():
    """Antes era `require_client_access`: o proprio cliente editava o proprio
    `status` e se promovia a `active` sem passar por pagamento."""
    antes = _ler()
    r = client.patch("/clients/1", json={"status": "active"}, headers=CLIENTE_1)
    assert r.status_code == 403
    assert _ler() == antes


def test_sem_autenticacao_nao_edita():
    assert client.patch("/clients/1", json={"name": "X"}).status_code == 401


# -------------------------------------------------------------------- bordas

def test_cliente_inexistente_404():
    r = client.patch("/clients/9999", json={"name": "X"}, headers=ADMIN)
    assert r.status_code == 404


def test_payload_sem_campo_editavel_400():
    r = client.patch("/clients/1", json={"campo_inventado": "x"}, headers=ADMIN)
    assert r.status_code == 400


def test_resposta_devolve_o_registro_atualizado():
    """A tela recarrega a partir desta resposta; faltar campo apaga dado na UI."""
    r = client.patch("/clients/1", json={"name": "Ana Final"}, headers=ADMIN)
    corpo = r.json()
    for campo in ("id", "name", "email", "phone", "objective", "status", "age",
                  "weight", "height"):
        assert campo in corpo, f"a resposta precisa trazer {campo}"
    assert corpo["name"] == "Ana Final"
