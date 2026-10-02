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
        # Sem plano ativo, `client_plan_id` resolve para 0 — a convenção de
        # `workout_completions`. A tabela nem existe nesta suíte, e isso é
        # parte do que se verifica: a rota não pode depender dela.
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
