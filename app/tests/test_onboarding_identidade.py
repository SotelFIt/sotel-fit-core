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
from sqlalchemy import create_engine, event
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


# Varias consultas do produto usam `NOW()`, que e do Postgres. Em vez de
# reescrever o SQL de producao so para o teste rodar — o que mediria um codigo
# diferente do que esta no ar —, a funcao e registrada aqui. O SQL exercitado e
# exatamente o mesmo.
@event.listens_for(engine, "connect")
def _registra_now(dbapi_conn, _):
    dbapi_conn.create_function(
        "NOW", 0, lambda: __import__("datetime").datetime.utcnow().isoformat(sep=" "))
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
        # O caminho de envio grava rastreio e auditoria. Em producao estas
        # tabelas existem; sem elas o teste mediria um erro de ambiente.
        c.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS whatsapp_events (id INTEGER PRIMARY KEY,"
            " client_id INTEGER, message_sid TEXT, status TEXT, error_code TEXT,"
            " to_phone TEXT, context TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)")
        c.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS admin_audit_log (id INTEGER PRIMARY KEY,"
            " action TEXT, admin_id INTEGER, client_id INTEGER, details TEXT,"
            " created_at TIMESTAMP)")
        c.exec_driver_sql("DELETE FROM whatsapp_events")
        c.exec_driver_sql("DELETE FROM admin_audit_log")
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


def test_token_INVALIDO_e_RECUSADO_nao_vira_anonimo():
    """Credencial apresentada e recusada e 401, nao "sem identidade".

    Degradar para anonimo e pior do que recusar: quem mandou um token esta
    afirmando uma identidade, e tratar a afirmacao falha como ausencia faria a
    requisicao seguir por um caminho que a pessoa nao pediu.
    """
    r = concluir(headers={"Authorization": "Bearer nao.e.um.token"},
                 telefone=ALUNA_FONE)
    assert r.status_code == 401, f"deu {r.status_code}: {r.text}"
    assert leads() == [], "recusou e mesmo assim gravou"
    assert dict((c[0], c[2]) for c in clientes())[ALUNA] == "onboarding",         "status do cadastro foi alterado por uma credencial recusada"


def test_token_invalido_com_telefone_de_OUTRO_cadastro_nao_conclui_o_dele():
    """O caminho por telefone nao pode ser alcancado por quem apresentou
    credencial ruim — nem com o numero de outra pessoa."""
    r = concluir(headers={"Authorization": "Bearer nao.e.um.token"},
                 telefone=OUTRO_FONE)
    assert r.status_code == 401
    assert leads() == []
    assert status(OUTRO)["onboarding_completed"] is False
    assert dict((c[0], c[2]) for c in clientes())[OUTRO] == "onboarding"


def test_token_EXPIRADO_e_recusado():
    import time
    import jwt
    from core.security import SECRET_KEY, ALGORITHM
    agora = int(time.time())
    expirado = jwt.encode(
        {"sub": ALUNA, "iat": agora - 7200, "exp": agora - 3600, "type": "access"},
        SECRET_KEY, algorithm=ALGORITHM)
    r = concluir(headers={"Authorization": f"Bearer {expirado}"}, telefone=ALUNA_FONE)
    assert r.status_code == 401, f"deu {r.status_code}: {r.text}"
    assert leads() == []


def test_esquema_de_autenticacao_desconhecido_e_recusado():
    r = concluir(headers={"Authorization": "Basic YWJjOjEyMw=="}, telefone=ALUNA_FONE)
    assert r.status_code == 401
    assert leads() == []


def test_SEM_credencial_segue_pelo_caminho_publico():
    """A contrapartida: ausencia de credencial continua valendo. Sem esta, a
    correcao viraria "so entra quem tem sessao" e quebraria o lead publico.

    Usa um telefone JA cadastrado de proposito: o caminho publico com telefone
    novo insere cliente com `NOW()`, que e funcao do Postgres e nao existe no
    SQLite. Esse ramo e exercitado na revalidacao em PostgreSQL.
    """
    r = concluir(telefone=OUTRO_FONE)
    assert r.status_code == 200, r.text
    assert [l[1] for l in leads()] == [None], "inventou vinculo sem identidade provada"
    # E o caminho antigo segue funcionando para quem nao tem sessao.
    assert status(OUTRO)["onboarding_completed"] is True


def test_sessao_de_cadastro_INEXISTENTE_nao_cai_no_caminho_por_telefone():
    r = concluir(headers=sessao(999999), telefone=ALUNA_FONE)
    assert r.status_code == 401, f"deu {r.status_code}: {r.text}"
    assert leads() == [], "gravou sob um cadastro que nao existe"
    assert status(ALUNA)["onboarding_completed"] is False


def test_sessao_de_cadastro_EXCLUIDO_nao_cai_no_caminho_por_telefone():
    """O token continua com assinatura valida; o que mudou foi o cadastro."""
    with engine.begin() as c:
        c.exec_driver_sql(
            f"UPDATE clients SET deleted_at = CURRENT_TIMESTAMP WHERE id = {ALUNA}")
    r = concluir(headers=sessao(ALUNA), telefone=ALUNA_FONE)
    assert r.status_code == 401, f"deu {r.status_code}: {r.text}"
    assert leads() == [], "cadastro excluido concluiu onboarding"


def test_token_MAGICO_nao_serve_como_sessao_de_dados():
    """O token do link e `type='magic'`: serve para trocar por sessao em
    /auth/magic-link/exchange, e NAO para falar direto com as rotas de dados.
    Sem isso, o link enviado por WhatsApp viraria credencial permanente."""
    r = concluir(headers={"Authorization": f"Bearer {create_magic_token(ALUNA)}"})
    # 401: o token foi APRESENTADO e e do tipo errado. Antes isto caia no
    # caminho anonimo e devolvia 400 por falta de telefone — a recusa era por
    # acidente, nao por decisao.
    assert r.status_code == 401, f"um token magico passou como sessao: {r.status_code}"
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


# ====================================== envio pelo admin, com Twilio simulado

def test_envio_identificado_leva_o_TOKEN_do_cadastro_no_link(monkeypatch):
    """Twilio SIMULADO: nenhuma mensagem real sai daqui.

    O que se verifica e o que a rota entrega ao fornecedor de mensagens: a
    variavel de link precisa ser o `/acesso#t=` DESTE cadastro. Era o elo que
    faltava — a rota antiga mandava um link generico, igual para todo mundo.
    """
    enviados = {}

    class MensagemFalsa:
        sid = "SM_simulado"
        status = "queued"

    class MensagensFalsas:
        def create(self, **kw):
            enviados.update(kw)
            return MensagemFalsa()

    class TwilioFalso:
        def __init__(self, *a, **kw):
            self.messages = MensagensFalsas()

    import routers.admin as admin
    monkeypatch.setattr(admin, "TwilioClient", TwilioFalso)
    monkeypatch.setenv("TWILIO_TEMPLATE_ONBOARDING", "HX_template_simulado")
    monkeypatch.setenv("CLIENT_APP_URL", "https://app.exemplo.invalid")

    r = client.post(f"/admin/twilio/resend-onboarding/{ALUNA}", headers=ADMIN)
    assert r.status_code == 200, r.text

    import json as _json
    variaveis = _json.loads(enviados["content_variables"])
    link = variaveis["2"]
    assert "/acesso#t=" in link, f"o link nao identifica o cadastro: {link}"

    # O token do link abre a sessao DESTE cadastro, e de nenhum outro.
    from core.security import verify_magic_token
    assert verify_magic_token(link.split("#t=")[1]) == ALUNA

    # E vai para o telefone do CADASTRO, nao para um informado na chamada.
    assert ALUNA_FONE.replace("+", "") in enviados["to"].replace("+", "")


def test_envio_identificado_recusa_cadastro_sem_telefone(monkeypatch):
    with engine.begin() as c:
        c.exec_driver_sql(f"UPDATE clients SET phone = NULL WHERE id = {ALUNA}")
    r = client.post(f"/admin/twilio/resend-onboarding/{ALUNA}", headers=ADMIN)
    assert r.status_code == 400


def test_rota_antiga_por_telefone_continua_para_leads(monkeypatch):
    """Quem ainda nao tem cadastro nao tem o que identificar. A tela de Leads
    continua usando esta rota — removê-la quebraria o fluxo de lead."""
    class TwilioFalso:
        def __init__(self, *a, **kw):
            self.messages = type("M", (), {"create": lambda s, **kw: type("X", (), {"sid": "SM", "status": "queued"})()})()

    import routers.admin as admin
    monkeypatch.setattr(admin, "TwilioClient", TwilioFalso)
    monkeypatch.setenv("TWILIO_TEMPLATE_ONBOARDING", "HX_template_simulado")
    r = client.post("/admin/twilio/resend-onboarding",
                    json={"phone": "+5511900001111"}, headers=ADMIN)
    assert r.status_code == 200, r.text
