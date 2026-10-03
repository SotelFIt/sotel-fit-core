"""
Registro de carga por série — WORKOUT-CARGA-001.

A capacidade que `WORKOUT_SPEC.md` §8 registrava como **MISSING DATA**: a
referência visual mostrava "Carga anterior 32 kg" e não havia campo de carga em
lugar nenhum do produto.

O que estes testes protegem, em uma frase cada:

  1. a carga sobrevive a recarregar e a retomar o treino;
  2. regravar a mesma série CORRIGE, não duplica;
  3. vírgula e ponto são o mesmo número — é vírgula que o teclado oferece;
  4. ausência de carga nunca vira zero;
  5. a carga anterior vem de registro REAL, e sem histórico o mapa vem vazio;
  6. o mesmo exercício prescrito duas vezes são duas cargas, não uma;
  7. republicar o plano não mistura a carga de hoje com a prescrição antiga;
  8. um aluno não lê nem grava a carga de outro;
  9. nada disto depende do fornecedor de vídeo.

O override de `get_db` é aplicado por TESTE e restaurado no fim: seis módulos
sobrescrevem essa dependência no import e o último importado ganha. O token de
admin é lido do módulo de segurança, não do ambiente, porque
`core/security.py` o captura uma vez no import e o ambiente muda durante a
coleta.
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
from core.security import create_access_token
from models.client import Client  # noqa: F401
from models.exercise_set_log import ExerciseSetLog
from main import app

ADMIN = {"x-api-key": seguranca.LANDBOT_SECRET_TOKEN}
ALUNO = {"Authorization": f"Bearer {create_access_token(1)}"}
OUTRO = {"Authorization": f"Bearer {create_access_token(2)}"}

HOJE = "2026-10-02"
ONTEM = "2026-10-01"
SEMANA_PASSADA = "2026-09-25"

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


@pytest.fixture(autouse=True)
def _base():
    anterior = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db

    Base.metadata.create_all(engine, tables=[Client.__table__, ExerciseSetLog.__table__])
    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM exercise_set_logs")
        conn.exec_driver_sql("DELETE FROM clients")
        # `deleted_at` é criada por migrate.py em produção; reproduzida aqui
        # para o teste exercitar o MESMO caminho de autorização.
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(clients)")]
        if "deleted_at" not in cols:
            conn.exec_driver_sql("ALTER TABLE clients ADD COLUMN deleted_at TIMESTAMP")
        conn.exec_driver_sql(
            "INSERT INTO clients (id, name, email, phone, status, created_at) VALUES"
            " (1,'Aluno Um','um@exemplo.invalid','+5511900000001','active',CURRENT_TIMESTAMP),"
            " (2,'Aluno Dois','dois@exemplo.invalid','+5511900000002','active',CURRENT_TIMESTAMP)"
        )
        # `client_plans` EXISTE, como em produção.
        #
        # Antes esta suíte não criava a tabela, e a consulta do plano falhava
        # com "no such table". O código antigo engolia qualquer exceção e
        # devolvia 0, então os testes passavam apoiados no próprio defeito que
        # a revisão apontou. Com a tabela no lugar, "sem plano ativo" passa a
        # ser uma linha ausente — ausência de verdade — e falha de consulta
        # volta a ser outra coisa, que os testes dedicados forçam de propósito.
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS client_plans ("
            " id INTEGER PRIMARY KEY, client_id INTEGER, content TEXT,"
            " status TEXT, published_content TEXT, enrichment_json TEXT,"
            " created_at TIMESTAMP)"
        )
        conn.exec_driver_sql("DELETE FROM client_plans")
    try:
        yield
    finally:
        if anterior is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = anterior


def _serie(**kw):
    corpo = {
        "workout_key": "A",
        "occurrence_key": "a-1",
        "exercise_name": "Remada sentada",
        "library_ref": "remada-sentada",
        "set_index": 1,
        "performed_date": HOJE,
        "weight_kg": 32,
    }
    corpo.update(kw)
    return corpo


def _gravar(headers=ALUNO, cid=1, **kw):
    return client.put(f"/clients/{cid}/set-logs", json=_serie(**kw), headers=headers)


def _linhas():
    with engine.begin() as c:
        return c.exec_driver_sql(
            "SELECT occurrence_key, set_index, performed_date, weight_kg"
            " FROM exercise_set_logs ORDER BY occurrence_key, set_index"
        ).fetchall()


# ============================================================ persistência

def test_a_carga_gravada_persiste():
    r = _gravar()
    assert r.status_code == 200, r.text
    assert r.json()["weight_kg"] == 32.0
    assert len(_linhas()) == 1, "respondeu 200 mas nao gravou"


def test_recarregar_a_tela_devolve_o_que_foi_gravado():
    """O teste do requisito "ao recarregar, os valores permanecem"."""
    _gravar(set_index=1, weight_kg=32)
    _gravar(set_index=2, weight_kg=34)

    r = client.get("/clients/1/set-logs", params={"workout_key": "A",
                                                 "performed_date": HOJE}, headers=ALUNO)
    assert r.status_code == 200, r.text
    itens = r.json()["itens"]
    assert [(i["set_index"], i["weight_kg"]) for i in itens] == [(1, 32.0), (2, 34.0)]


def test_regravar_a_mesma_serie_CORRIGE_e_nao_duplica():
    """O aluno errou o número, ou subiu a carga na segunda tentativa."""
    _gravar(weight_kg=32)
    r = _gravar(weight_kg=36)
    assert r.status_code == 200
    assert r.json()["weight_kg"] == 36.0
    assert len(_linhas()) == 1, "virou duas linhas"


def test_reenvio_apos_falha_de_rede_e_seguro():
    """PUT idempotente por identidade: reenviar o mesmo corpo N vezes é uma
    série só. Sem isso, a tela precisaria de chave de idempotência própria."""
    for _ in range(4):
        assert _gravar(weight_kg=32).status_code == 200
    assert len(_linhas()) == 1


# ================================================= vírgula, ponto e ausência

def test_virgula_e_ponto_sao_o_mesmo_numero():
    """O teclado do celular brasileiro oferece VÍRGULA. Recusá-la obrigaria a
    tela a traduzir antes de enviar, e a regra passaria a existir em dois
    lugares, com chance de divergir."""
    assert _gravar(weight_kg="32,5").json()["weight_kg"] == 32.5
    assert _gravar(set_index=2, weight_kg="32.5").json()["weight_kg"] == 32.5


def test_peso_como_texto_simples_e_aceito():
    assert _gravar(weight_kg="40").json()["weight_kg"] == 40.0


def test_sem_carga_e_NULO_e_nao_zero():
    """Há exercício sem carga externa (prancha, flexão). A série existe e o
    peso não. *Ausência nunca vira zero* — e zero é um valor que alguém pode
    registrar de propósito (barra vazia)."""
    r = _gravar(exercise_name="Prancha", weight_kg=None)
    assert r.status_code == 200, r.text
    assert r.json()["weight_kg"] is None
    assert _linhas()[0][3] is None, "ausencia virou zero no banco"


def test_texto_vazio_tambem_e_ausencia():
    assert _gravar(weight_kg="").json()["weight_kg"] is None


def test_zero_continua_sendo_zero():
    r = _gravar(weight_kg=0)
    assert r.status_code == 200
    assert r.json()["weight_kg"] == 0.0


def test_peso_invalido_e_recusado_sem_gravar():
    # `inf` e `nan` entram como TEXTO porque é a única forma de chegarem: não
    # são JSON válido como número, e o próprio serializador recusa antes de
    # sair do cliente. Como texto, chegam — e precisam ser barrados aqui.
    for ruim in ("abc", "32,5,5", "inf", "-inf", "nan", "32 kg"):
        r = _gravar(weight_kg=ruim)
        assert r.status_code == 422, f"{ruim!r} passou: {r.status_code}"
    assert _linhas() == [], "recusou e mesmo assim gravou"


def test_peso_negativo_e_absurdo_sao_recusados():
    assert _gravar(weight_kg=-1).status_code == 422
    assert _gravar(weight_kg=99999).status_code == 422
    assert _linhas() == []


# ======================================================= identidade da série

def test_o_mesmo_exercicio_duas_vezes_sao_duas_cargas():
    """Leg Press no aquecimento e no bloco principal é prescrição diferente,
    com carga diferente. Juntar pelo nome somaria as duas num número só."""
    _gravar(occurrence_key="a-1", exercise_name="Leg Press", weight_kg=80)
    _gravar(occurrence_key="a-4", exercise_name="Leg Press", weight_kg=140)

    linhas = _linhas()
    assert len(linhas) == 2
    assert {l[0]: l[3] for l in linhas} == {"a-1": 80.0, "a-4": 140.0}


def test_series_diferentes_sao_registros_diferentes():
    _gravar(set_index=1, weight_kg=30)
    _gravar(set_index=2, weight_kg=32)
    _gravar(set_index=3, weight_kg=34)
    assert len(_linhas()) == 3


def test_o_mesmo_treino_noutro_dia_e_registro_novo():
    _gravar(performed_date=ONTEM, weight_kg=30)
    _gravar(performed_date=HOJE, weight_kg=32)
    assert len(_linhas()) == 2, "sobrescreveu o dia anterior"


def test_treinos_diferentes_nao_se_misturam():
    _gravar(workout_key="A", weight_kg=30)
    _gravar(workout_key="B", weight_kg=50)
    assert len(_linhas()) == 2


# ========================================================== carga anterior

def test_sem_historico_o_mapa_vem_VAZIO():
    """O estado vazio é o requisito: sem registro real, a tela não pode
    mostrar número nenhum. Devolver 0 aqui seria inventar carga."""
    r = client.get("/clients/1/set-logs/anterior", headers=ALUNO)
    assert r.status_code == 200
    assert r.json()["anterior"] == {}


def test_a_carga_anterior_vem_de_registro_real():
    _gravar(performed_date=SEMANA_PASSADA, weight_kg=30)

    r = client.get("/clients/1/set-logs/anterior",
                   params={"antes_de": HOJE}, headers=ALUNO)
    a = r.json()["anterior"]["a-1"]
    assert a["weight_kg"] == 30.0
    assert a["performed_date"] == SEMANA_PASSADA
    assert a["exercise_name"] == "Remada sentada"


def test_a_carga_anterior_ignora_o_proprio_dia():
    """Senão "anterior" viraria "o que acabei de digitar" e o número mudaria
    debaixo do aluno enquanto ele treina."""
    _gravar(performed_date=SEMANA_PASSADA, weight_kg=30)
    _gravar(performed_date=HOJE, weight_kg=99)

    a = client.get("/clients/1/set-logs/anterior",
                   params={"antes_de": HOJE}, headers=ALUNO).json()["anterior"]
    assert a["a-1"]["weight_kg"] == 30.0, "usou a carga de hoje como anterior"


def test_a_carga_anterior_e_do_dia_mais_recente():
    _gravar(performed_date=SEMANA_PASSADA, weight_kg=30)
    _gravar(performed_date=ONTEM, weight_kg=34)

    a = client.get("/clients/1/set-logs/anterior",
                   params={"antes_de": HOJE}, headers=ALUNO).json()["anterior"]
    assert a["a-1"]["weight_kg"] == 34.0
    assert a["a-1"]["performed_date"] == ONTEM


def test_no_dia_anterior_vale_a_serie_mais_pesada():
    """A série mais pesada é a referência para decidir quanto pôr hoje; a
    média diluiria o aquecimento no número."""
    _gravar(performed_date=ONTEM, set_index=1, weight_kg=20)
    _gravar(performed_date=ONTEM, set_index=2, weight_kg=34)
    _gravar(performed_date=ONTEM, set_index=3, weight_kg=30)

    a = client.get("/clients/1/set-logs/anterior",
                   params={"antes_de": HOJE}, headers=ALUNO).json()["anterior"]
    assert a["a-1"]["weight_kg"] == 34.0
    assert a["a-1"]["set_index"] == 2


def test_serie_sem_carga_nao_entra_na_carga_anterior():
    """Prancha não tem carga anterior. Entrar com `None` faria a tela exibir
    um campo vazio apresentado como histórico."""
    _gravar(performed_date=ONTEM, occurrence_key="a-9",
            exercise_name="Prancha", weight_kg=None)

    a = client.get("/clients/1/set-logs/anterior",
                   params={"antes_de": HOJE}, headers=ALUNO).json()["anterior"]
    assert "a-9" not in a


# ===================================================== versão do plano

def test_a_listagem_do_dia_nao_traz_carga_de_plano_substituido():
    """`client_plan_id` resolve para 0 nesta suíte (sem `client_plans`). O que
    se verifica aqui é que a listagem filtra pela versão vigente — uma linha
    gravada sob outra versão não reaparece preenchida numa prescrição nova."""
    _gravar(weight_kg=32)
    with engine.begin() as c:
        c.exec_driver_sql("UPDATE exercise_set_logs SET client_plan_id = 77")

    itens = client.get("/clients/1/set-logs",
                       params={"performed_date": HOJE}, headers=ALUNO).json()["itens"]
    assert itens == [], "carga de outra versao do plano reapareceu na tela"


def test_a_carga_anterior_ATRAVESSA_versoes_do_plano():
    """O outro lado: republicar o plano não apaga o histórico de carga. O que
    amarra é a ocorrência, não a versão — senão toda republicação zeraria a
    referência do aluno."""
    _gravar(performed_date=ONTEM, weight_kg=34)
    with engine.begin() as c:
        c.exec_driver_sql("UPDATE exercise_set_logs SET client_plan_id = 77")

    a = client.get("/clients/1/set-logs/anterior",
                   params={"antes_de": HOJE}, headers=ALUNO).json()["anterior"]
    assert a["a-1"]["weight_kg"] == 34.0, "republicar o plano apagou a referencia"


# ============================================================== acesso

def test_um_aluno_nao_grava_a_carga_de_outro():
    r = _gravar(headers=OUTRO, cid=1)
    assert r.status_code == 403
    assert _linhas() == []


def test_um_aluno_nao_le_a_carga_de_outro():
    _gravar(weight_kg=32)
    assert client.get("/clients/1/set-logs", headers=OUTRO).status_code == 403
    assert client.get("/clients/1/set-logs/anterior", headers=OUTRO).status_code == 403


def test_sem_autenticacao_nao_grava_nem_le():
    assert client.put("/clients/1/set-logs", json=_serie()).status_code == 401
    assert client.get("/clients/1/set-logs").status_code == 401


def test_aluno_EXCLUIDO_perde_o_acesso_mesmo_com_token_valido():
    """O token continua com assinatura válida; o que mudou foi o cadastro."""
    with engine.begin() as c:
        c.exec_driver_sql("UPDATE clients SET deleted_at = CURRENT_TIMESTAMP WHERE id = 1")
    assert _gravar().status_code == 401
    assert client.get("/clients/1/set-logs", headers=ALUNO).status_code == 401


def test_admin_consegue_ler_a_carga_do_aluno():
    """O treinador precisa ver a progressão para ajustar a prescrição."""
    _gravar(weight_kg=32)
    r = client.get("/clients/1/set-logs", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["itens"][0]["weight_kg"] == 32.0


# ================================================ independência do vídeo

def test_o_registro_de_carga_nao_depende_do_fornecedor_de_video():
    """Caminhos separados de propósito: a demonstração pode estar fora do ar,
    sem credencial ou com a cota estourada, e o aluno continua registrando o
    que levantou. Este módulo não importa nada de `services.ymove`."""
    import routers.exercise_set_log as rota
    fonte = open(rota.__file__, encoding="utf-8").read()
    codigo = "\n".join(
        l for l in fonte.splitlines() if not l.strip().startswith("#")
    )
    assert "ymove" not in codigo.lower().split('"""')[-1], \
        "o registro de carga nao pode importar o fornecedor de video"

    # E, de fato, grava sem nenhuma credencial de vídeo no ambiente.
    anterior = os.environ.pop("YMOVE_API_KEY", None)
    try:
        assert _gravar(weight_kg=32).status_code == 200
    finally:
        if anterior is not None:
            os.environ["YMOVE_API_KEY"] = anterior


# =========================================================================
# CORRIDA NA GRAVACAO E FALHA DE CONSULTA DO PLANO
#
# Reproduzido com o BANCO e a ROTA reais, nao com a funcao isolada: a
# interleaving e forcada injetando a linha concorrente dentro do commit, de
# outra conexao, de modo que a restricao unica do banco arbitre de verdade.
# =========================================================================

import sqlalchemy.orm as _orm


def _vence_a_corrida(monkeypatch, peso_do_vencedor=30.0, apenas_a_primeira=True):
    """Faz OUTRA aba gravar primeiro, no meio do caminho desta requisicao."""
    estado = {"n": 0}
    original = _orm.Session.commit

    def commit(self):
        if not apenas_a_primeira or estado["n"] == 0:
            estado["n"] += 1
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "INSERT OR IGNORE INTO exercise_set_logs"
                    " (client_id, client_plan_id, workout_key, occurrence_key,"
                    "  exercise_name, set_index, performed_date, weight_kg,"
                    "  created_at, updated_at)"
                    " VALUES (1, 0, 'A', 'a-1', 'Remada sentada', 1, '2026-10-02',"
                    f" {peso_do_vencedor}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
        return original(self)

    monkeypatch.setattr(_orm.Session, "commit", commit)
    return estado


def test_corrida_NAO_confirma_um_valor_que_nao_foi_gravado(monkeypatch):
    """O achado da revisao.

    Duas requisicoes criam a mesma serie. Uma grava 30; a outra manda 34,5,
    perde a corrida e — antes da correcao — recebia 200 com 30 kg. O aluno via
    "Carga salva" e o que ficou foi o numero da outra aba.

    A regra que este teste fixa: se a resposta for sucesso, ela precisa
    descrever o que esta REALMENTE no banco, e o que esta no banco precisa ser
    o que esta requisicao enviou. Qualquer outro desfecho e erro explicito.
    """
    _vence_a_corrida(monkeypatch, peso_do_vencedor=30.0)

    r = _gravar(weight_kg=34.5)

    linhas = _linhas()
    assert len(linhas) == 1, "a identidade da serie deixou de ser unica"
    gravado = linhas[0][3]

    if r.status_code == 200:
        assert r.json()["weight_kg"] == 34.5, (
            "confirmou sucesso com um valor que esta requisicao nao enviou"
        )
        assert gravado == 34.5, "respondeu 34,5 e o banco ficou com outro valor"
    else:
        # Desfecho explicito tambem e aceitavel — o que nao pode e sucesso falso.
        assert r.status_code in (409, 503), f"erro inesperado: {r.status_code}"
        assert gravado == 30.0


def test_corrida_nao_duplica_a_serie(monkeypatch):
    _vence_a_corrida(monkeypatch, peso_do_vencedor=30.0)
    _gravar(weight_kg=34.5)
    assert len(_linhas()) == 1


def test_reenvio_apos_corrida_continua_idempotente(monkeypatch):
    """Depois da disputa, reenviar o mesmo corpo nao pode criar outra linha."""
    _vence_a_corrida(monkeypatch, peso_do_vencedor=30.0)
    _gravar(weight_kg=34.5)
    _gravar(weight_kg=34.5)
    _gravar(weight_kg=34.5)
    assert len(_linhas()) == 1


def test_falha_de_banco_que_NAO_e_conflito_nao_vira_sucesso(monkeypatch):
    """O `except Exception` tratava qualquer falha como corrida.

    Com uma linha da mesma identidade ja existente, um erro de banco qualquer
    (disco cheio, conexao perdida) encontrava essa linha na releitura e
    devolvia 200 — relatando como gravado algo que nunca foi.
    """
    _gravar(weight_kg=30.0)  # a linha existe

    original = _orm.Session.commit

    def commit_quebrado(self):
        raise RuntimeError("falha de banco que nao e conflito de unicidade")

    monkeypatch.setattr(_orm.Session, "commit", commit_quebrado)

    r = _gravar(weight_kg=34.5)
    assert r.status_code >= 500, f"falha de banco virou {r.status_code}"
    assert _linhas()[0][3] == 30.0, "o valor antigo foi alterado apesar da falha"


# ------------------------------------------- falha ao resolver o plano ativo

def test_falha_ao_CONSULTAR_o_plano_nao_grava_sob_plano_0(monkeypatch):
    """O outro achado.

    `_plano_ativo` devolvia 0 para qualquer excecao, misturando "consulta
    falhou" com "este aluno nao tem plano ativo" — que e situacao legitima e
    documentada (mesma convencao de `workout_completions`).

    A diferenca importa: com a consulta falhando, gravar sob plano 0 guarda a
    carga numa versao que nao e a do treino que o aluno esta fazendo. Na
    proxima leitura ela some, porque a listagem filtra pela versao vigente.
    """
    import routers.exercise_set_log as rota

    def consulta_quebrada(self, *a, **kw):
        raise RuntimeError("banco indisponivel")

    monkeypatch.setattr(_orm.Session, "execute", consulta_quebrada)

    r = _gravar(weight_kg=34.5)
    assert r.status_code == 503, f"falha de consulta virou {r.status_code}"
    assert _linhas() == [], "gravou mesmo sem saber a que plano a carga pertence"


def test_falha_ao_consultar_o_plano_nao_devolve_listagem_vazia_como_valida(monkeypatch):
    """Lista vazia por falha de consulta e indistinguivel de "nada registrado".
    A tela limparia os campos do aluno achando que nao havia nada."""
    _gravar(weight_kg=30.0)

    def consulta_quebrada(self, *a, **kw):
        raise RuntimeError("banco indisponivel")

    monkeypatch.setattr(_orm.Session, "execute", consulta_quebrada)

    r = client.get("/clients/1/set-logs", params={"performed_date": HOJE}, headers=ALUNO)
    assert r.status_code == 503, f"listagem com banco fora devolveu {r.status_code}"


def test_aluno_SEM_plano_ativo_continua_gravando_sob_plano_0():
    """O comportamento legitimo, que NAO muda.

    Ausencia de plano ativo e situacao normal e documentada: `0` mantem a
    chave natural utilizavel, porque NULL nao compara igual em SQL. A correcao
    separa falha de consulta de ausencia — nao redefine a ausencia.
    """
    r = _gravar(weight_kg=32.0)
    assert r.status_code == 200, r.text
    with engine.begin() as c:
        plano = c.exec_driver_sql(
            "SELECT client_plan_id FROM exercise_set_logs").fetchone()[0]
    assert plano == 0, "aluno sem plano ativo deixou de gravar sob plano 0"


# ==================================================================
# VERSAO DO PLANO — agora com `client_plans` de verdade na suite
# ==================================================================

def _publicar_plano(pid: int, quando: str = "2026-09-01 10:00:00"):
    """Publica uma versao do plano para o cliente 1 e desativa as anteriores."""
    with engine.begin() as c:
        c.exec_driver_sql("UPDATE client_plans SET status = 'archived' WHERE client_id = 1")
        c.exec_driver_sql(
            "INSERT INTO client_plans (id, client_id, content, status, created_at)"
            f" VALUES ({pid}, 1, 'plano', 'active', '{quando}')"
        )


def test_a_carga_e_gravada_sob_a_versao_ATIVA_do_plano():
    _publicar_plano(10)
    r = _gravar(weight_kg=32)
    assert r.status_code == 200, r.text
    with engine.begin() as c:
        plano = c.exec_driver_sql(
            "SELECT client_plan_id FROM exercise_set_logs").fetchone()[0]
    assert plano == 10, f"gravou sob o plano {plano}"


def test_republicar_o_plano_NAO_mistura_o_registro_do_dia():
    """O treinador republica no meio do dia. A carga gravada sob a versao
    antiga nao pode reaparecer preenchida numa prescricao que mudou — os
    exercicios, a ordem e as series podem ser outros."""
    _publicar_plano(10)
    _gravar(weight_kg=32)

    _publicar_plano(11, quando="2026-09-02 10:00:00")
    itens = client.get("/clients/1/set-logs",
                       params={"performed_date": HOJE}, headers=ALUNO).json()["itens"]
    assert itens == [], "carga da versao anterior reapareceu na prescricao nova"


def test_republicar_o_plano_NAO_apaga_a_carga_anterior():
    """O outro lado, e o que o aluno percebe: a referencia de quanto ele
    levantou continua valendo mesmo que o treinador tenha mexido no plano.
    O que amarra e a ocorrencia, nao a versao."""
    _publicar_plano(10)
    _gravar(performed_date=ONTEM, weight_kg=34)

    _publicar_plano(11, quando="2026-09-02 10:00:00")
    a = client.get("/clients/1/set-logs/anterior",
                   params={"antes_de": HOJE}, headers=ALUNO).json()["anterior"]
    assert a["a-1"]["weight_kg"] == 34.0, "republicar o plano apagou a referencia"


def test_a_mesma_serie_em_versoes_diferentes_sao_registros_diferentes():
    """Nao e correcao: e outra prescricao. Sobrescrever perderia o historico
    de qual carga pertencia a qual versao do treino."""
    _publicar_plano(10)
    _gravar(weight_kg=32)
    _publicar_plano(11, quando="2026-09-02 10:00:00")
    _gravar(weight_kg=36)

    with engine.begin() as c:
        linhas = c.exec_driver_sql(
            "SELECT client_plan_id, weight_kg FROM exercise_set_logs"
            " ORDER BY client_plan_id").fetchall()
    assert linhas == [(10, 32.0), (11, 36.0)], linhas


def test_corrida_sob_plano_ativo_real_tambem_nao_confirma_valor_alheio(monkeypatch):
    """A corrida com `client_plan_id` de verdade, nao o 0 do caso sem plano."""
    _publicar_plano(10)

    import sqlalchemy.orm as _orm
    estado = {"n": 0}
    original = _orm.Session.commit

    def commit(self):
        if estado["n"] == 0:
            estado["n"] += 1
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "INSERT OR IGNORE INTO exercise_set_logs"
                    " (client_id, client_plan_id, workout_key, occurrence_key,"
                    "  exercise_name, set_index, performed_date, weight_kg,"
                    "  created_at, updated_at)"
                    " VALUES (1, 10, 'A', 'a-1', 'Remada sentada', 1, '2026-10-02',"
                    " 30.0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
        return original(self)

    monkeypatch.setattr(_orm.Session, "commit", commit)

    r = _gravar(weight_kg=34.5)
    with engine.begin() as c:
        linhas = c.exec_driver_sql(
            "SELECT client_plan_id, weight_kg FROM exercise_set_logs").fetchall()
    assert len(linhas) == 1
    if r.status_code == 200:
        assert r.json()["weight_kg"] == 34.5
        assert linhas[0] == (10, 34.5)
    else:
        assert r.status_code == 409


def test_a_resposta_e_LIDA_do_banco_depois_do_commit():
    """A exigencia literal: a resposta de sucesso descreve o que ESTA no banco.

    Quem garante isso nao e o `db.refresh` explicito: e o `expire_on_commit`
    do `sessionmaker` (ligado por padrao, conferido), que invalida os objetos
    no commit e faz o acesso ao atributo reler do banco. Removi a linha do
    `refresh` para checar, e este teste continuou passando — a garantia vem da
    sessao, nao dela. A linha fica por ser explicita, nao por ser o mecanismo.

    O gatilho existe para que a diferenca seja OBSERVAVEL: o banco grava 99
    enquanto a requisicao enviou 34,5. Uma rota que devolvesse o valor de
    memoria responderia 34,5 e estaria mentindo sobre o que ficou gravado —
    a mesma classe de confirmacao falsa que esta correcao elimina.
    """
    with engine.begin() as c:
        c.exec_driver_sql(
            "CREATE TRIGGER t_mexe AFTER INSERT ON exercise_set_logs"
            " BEGIN UPDATE exercise_set_logs SET weight_kg = 99.0"
            " WHERE id = NEW.id; END"
        )
    try:
        r = _gravar(weight_kg=34.5)
        assert r.status_code == 200, r.text
        no_banco = _linhas()[0][3]
        assert no_banco == 99.0, "o gatilho nao rodou; o teste nao esta medindo nada"
        assert r.json()["weight_kg"] == no_banco, (
            "a resposta nao descreve o que ficou no banco"
        )
    finally:
        with engine.begin() as c:
            c.exec_driver_sql("DROP TRIGGER IF EXISTS t_mexe")
