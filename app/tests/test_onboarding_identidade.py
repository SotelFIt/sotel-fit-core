"""
Identidade do onboarding — ONBOARDING-IDENTIDADE.

O defeito, reproduzido em PostgreSQL antes de qualquer correcao: a pessoa era
cadastrada no admin, recebia o link do "Enviar onboarding", preenchia e
concluia — e voltava ao formulario ao reabrir o app.

A causa nao era o formulario nem a pessoa. Era a cadeia de identidade:

  link do admin ....... template fixo do Twilio, igual para todo mundo
  tela de onboarding .. so reconhecia sessao vinda do Stripe (?session_id=)
  POST /onboarding/lead  nao aceitava client_id; casava por TELEFONE DIGITADO
  GET  /status/{id} ... resolvia por clients.phone -> lead_onboardings.phone

Com telefone divergente, o backend respondia 200 e criava um SEGUNDO cadastro
em silencio. Com telefone em branco, respondia 200 e nao ligava nada. Nos dois
casos `/status` continuava dizendo "onboarding", e o ProtectedRoute mandava a
pessoa de volta ao formulario.

Estes testes seguram a correcao: quando ha sessao valida, ela — e nao o campo
de telefone — decide de quem sao as respostas.

Isolamento igual ao dos outros modulos: SQLite in-memory com override de
get_db no app REAL, aplicado por teste e restaurado no fim.
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
import core.security as seguranca
from core.security import create_access_token, create_magic_token
from models.client import Client  # noqa: F401
from models.lead_onboarding import LeadOnboarding
from models.conversation_state import ConversationState  # noqa: F401
from main import app

ADMIN = {"x-api-key": seguranca.LANDBOT_SECRET_TOKEN}

# A aluna do caso: cadastrada no admin, com telefone em E.164.
ALUNA = 9001
ALUNA_FONE = "+5517999990001"
# Outro cadastro, para provar que ninguem grava onboarding alheio.
OUTRO = 9002
OUTRO_FONE = "+5511988887777"

engine = create_engine("sqlite:///:memory:",
                       connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
Sessao = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = Sessao()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _base():
    anterior = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db

    Base.metadata.create_all(engine, tables=[
        Client.__table__, LeadOnboarding.__table__, ConversationState.__table__])
    with engine.begin() as c:
        c.exec_driver_sql("DELETE FROM lead_onboardings")
        c.exec_driver_sql("DELETE FROM conversation_states")
        c.exec_driver_sql("DELETE FROM clients")
        # `client_plans` existe em producao e `/status` a consulta. Sem ela aqui,
        # o teste mediria um erro de ambiente em vez do comportamento.
        c.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS client_plans (id INTEGER PRIMARY KEY,"
            " client_id INTEGER, content TEXT, status TEXT, published_content TEXT,"
            " created_at TIMESTAMP)")
        c.exec_driver_sql("DELETE FROM client_plans")
        cols = [r[1] for r in c.exec_driver_sql("PRAGMA table_info(clients)")]
        if "updated_at" not in cols:
            c.exec_driver_sql("ALTER TABLE clients ADD COLUMN updated_at TIMESTAMP")
        c.exec_driver_sql(
            "INSERT INTO clients (id, name, email, phone, status, created_at) VALUES"
            f" ({ALUNA},'Aluna Ficticia','a@exemplo.invalid','{ALUNA_FONE}','onboarding',CURRENT_TIMESTAMP),"
            f" ({OUTRO},'Outro Aluno','b@exemplo.invalid','{OUTRO_FONE}','onboarding',CURRENT_TIMESTAMP)"
        )
    try:
        yield
    finally:
        if anterior is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = anterior


def sessao(cid):
    return {"Authorization": f"Bearer {create_access_token(cid)}"}


def concluir(headers=None, **campos):
    corpo = {"nome": "Aluna Ficticia", "email": "a@exemplo.invalid",
             "objetivo": "Emagrecer", "meta_principal": "Saude"}
    corpo.update(campos)
    return client.post("/onboarding/lead", json=corpo, headers=headers or {})


def leads():
    with engine.begin() as c:
        return c.exec_driver_sql(
            "SELECT id, client_id, phone FROM lead_onboardings ORDER BY id").fetchall()


def clientes():
    with engine.begin() as c:
        return c.exec_driver_sql(
            "SELECT id, phone, status FROM clients ORDER BY id").fetchall()


def status(cid):
    return client.get(f"/onboarding/status/{cid}").json()


# ====================================================== o caso relatado

def test_telefone_em_branco_COM_sessao_vincula_ao_cadastro():
    """O cenario C da reproducao: a pessoa deixou o WhatsApp vazio.

    Antes: 200, respostas soltas, nenhum cadastro tocado, volta ao formulario.
    Agora a sessao diz de quem sao as respostas, e o campo vazio nao atrapalha.
    """
    r = concluir(headers=sessao(ALUNA))
    assert r.status_code == 200, r.text
    assert [l[1] for l in leads()] == [ALUNA], "as respostas nao ficaram ligadas ao cadastro"
    assert status(ALUNA)["next_step"] == "waiting_plan"
    assert status(ALUNA)["onboarding_completed"] is True


def test_telefone_DIVERGENTE_nao_transfere_nem_duplica():
    """O cenario B: a pessoa digitou outro numero.

    Antes: 200, um SEGUNDO cadastro criado em silencio, e o original intacto
    em "onboarding". Editar o telefone nao pode mudar de quem e o onboarding.
    """
    antes = len(clientes())
    r = concluir(headers=sessao(ALUNA), telefone="11955554444")
    assert r.status_code == 200, r.text

    assert [l[1] for l in leads()] == [ALUNA], "o vinculo seguiu o telefone digitado"
    assert len(clientes()) == antes, "criou cadastro novo a partir do telefone digitado"
    assert status(ALUNA)["next_step"] == "waiting_plan"
    # E o telefone do OUTRO cadastro existente nao foi tocado.
    assert dict((c[0], c[2]) for c in clientes())[OUTRO] == "onboarding"


def test_telefone_de_OUTRO_aluno_nao_rouba_o_onboarding_dele():
    """Digitar o telefone de outra pessoa nao pode concluir o onboarding dela."""
    concluir(headers=sessao(ALUNA), telefone=OUTRO_FONE)

    assert [l[1] for l in leads()] == [ALUNA]
    assert status(OUTRO)["onboarding_completed"] is False, \
        "o onboarding do outro cadastro foi concluido por tabela"


def test_client_id_no_CORPO_e_ignorado():
    """A identidade vem da assinatura do token, nunca do que o navegador manda."""
    r = concluir(headers=sessao(ALUNA), client_id=OUTRO)
    assert r.status_code == 200, r.text
    assert [l[1] for l in leads()] == [ALUNA], "aceitou client_id do corpo"
    assert status(OUTRO)["onboarding_completed"] is False


# ====================================================== envio repetido

def test_envio_repetido_nao_duplica_cadastro():
    antes = len(clientes())
    for _ in range(3):
        assert concluir(headers=sessao(ALUNA), telefone=ALUNA_FONE).status_code == 200
    assert len(clientes()) == antes, "envio repetido criou cadastro"
    assert all(l[1] == ALUNA for l in leads()), "alguma resposta ficou sem vinculo"
    assert status(ALUNA)["next_step"] == "waiting_plan"


# ====================================================== sem sessao

def test_SEM_sessao_e_sem_telefone_e_recusado():
    """Era aqui que nascia a confirmacao falsa: sem sessao e sem telefone nao
    ha a quem ligar as respostas, e o backend respondia "ok" mesmo assim."""
    r = concluir()
    assert r.status_code == 400, f"deu {r.status_code}: {r.text}"
    assert leads() == [], "recusou e mesmo assim gravou"


def test_token_INVALIDO_cai_no_caminho_anonimo_sem_quebrar():
    """Token corrompido nao e erro de autenticacao nesta rota — e ausencia de
    identidade. Com telefone valido, o lead publico continua funcionando."""
    r = concluir(headers={"Authorization": "Bearer nao.e.um.token"},
                 telefone=ALUNA_FONE)
    assert r.status_code == 200, r.text
    # Sem identidade provada, o vinculo explicito NAO e inventado.
    assert [l[1] for l in leads()] == [None]
    # Mas o casamento por telefone (caminho antigo) segue valendo.
    assert status(ALUNA)["onboarding_completed"] is True


def test_token_invalido_SEM_telefone_e_recusado():
    r = concluir(headers={"Authorization": "Bearer nao.e.um.token"})
    assert r.status_code == 400
    assert leads() == []


def test_token_MAGICO_nao_serve_como_sessao_de_dados():
    """O token do link e `type='magic'`: serve para trocar por sessao em
    /auth/magic-link/exchange, e NAO para falar direto com as rotas de dados.
    Sem isso, o link enviado por WhatsApp viraria credencial permanente."""
    r = concluir(headers={"Authorization": f"Bearer {create_magic_token(ALUNA)}"})
    assert r.status_code == 400, "um token magico passou como sessao"
    assert leads() == []


# ====================================================== consulta de conclusao

def test_status_reconhece_o_vinculo_explicito_mesmo_sem_telefone():
    concluir(headers=sessao(ALUNA))
    with engine.begin() as c:
        assert c.exec_driver_sql(
            "SELECT phone FROM lead_onboardings").fetchone()[0] is None
    assert status(ALUNA)["onboarding_completed"] is True


def test_status_preserva_as_linhas_HISTORICAS_por_telefone():
    """Linhas anteriores a esta correcao tem client_id nulo. Elas continuam
    valendo pelo casamento de telefone — nada foi associado por aproximacao."""
    with engine.begin() as c:
        c.exec_driver_sql(
            "INSERT INTO lead_onboardings (client_id, phone, nome) VALUES"
            f" (NULL, '{ALUNA_FONE}', 'Historico')")
    assert status(ALUNA)["onboarding_completed"] is True


def test_status_de_quem_nao_concluiu_continua_dizendo_onboarding():
    """Sem esta, bastaria responder "concluido" para todo mundo e os outros
    testes passariam."""
    assert status(OUTRO)["onboarding_completed"] is False
    assert status(OUTRO)["next_step"] == "onboarding"


# ====================================================== link do admin

def test_link_do_admin_identifica_o_cadastro():
    """O link deixa de ser o mesmo para todo mundo.

    Nao enviamos WhatsApp aqui — o que se verifica e que a rota exige um
    cadastro existente e com telefone, que e a pre-condicao do link
    identificado.
    """
    assert client.post(f"/admin/twilio/resend-onboarding/{ALUNA}",
                       headers=ADMIN).status_code != 404
    assert client.post("/admin/twilio/resend-onboarding/99999",
                       headers=ADMIN).status_code == 404


def test_link_identificado_e_so_do_admin():
    r = client.post(f"/admin/twilio/resend-onboarding/{ALUNA}", headers=sessao(ALUNA))
    assert r.status_code == 403, f"um aluno emitiu link de outro: {r.status_code}"
