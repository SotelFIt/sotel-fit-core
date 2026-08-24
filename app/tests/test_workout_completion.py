"""
WORKOUT-DATA-001 — conclusão canônica e idempotente do treino.

O que estes testes protegem
---------------------------
A conclusão vivia só no `localStorage`. O backend recebia `POST /timeline/event`,
que insere sempre E conta eventos `workout` para disparar marcos de 5/10/20/50.
Em falha de transporte não dava para saber se o INSERT ocorreu; repetir podia
duplicar o evento e **disparar um marco falso**. Estes testes existem para que
isso não volte.

Isolamento: SQLite in-memory com override de `get_db` no app REAL, mesma
convenção de `test_exercise_api.py`.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault("JWT_SECRET_KEY", "ec/hBUFhntuNSkRbbVvo6CnWDOkXV2b8TMLI5vMcFd8=")
os.environ.setdefault("LANDBOT_SECRET_TOKEN", "token-admin-teste")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from datetime import date  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from core.database import Base, get_db  # noqa: E402
from core.security import create_access_token  # noqa: E402
from models.workout_completion import WorkoutCompletion  # noqa: E402,F401
from main import app  # noqa: E402

CLIENTE = 99
OUTRO = 77
H = {"Authorization": f"Bearer {create_access_token(CLIENTE)}"}
H_OUTRO = {"Authorization": f"Bearer {create_access_token(OUTRO)}"}

# SQLite em ARQUIVO, nao in-memory: o teste de corrida precisa de conexoes
# REAIS e independentes. Com `:memory:` + StaticPool todas as threads
# compartilham uma unica conexao, e o proprio driver aborta com
# `InterfaceError: bad parameter or other API misuse` antes de qualquer corrida
# acontecer — o teste passaria (ou falharia) sem nunca exercitar o que promete.
_DB = os.path.join(tempfile.gettempdir(), "sotel_workout_completion_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
engine = create_engine(
    f"sqlite:///{_DB}",
    connect_args={"check_same_thread": False, "timeout": 30},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)

# timeline_events não tem model ORM (é SQL cru no produto). A suíte materializa
# o mínimo do schema real para poder AFIRMAR quantos eventos foram criados.
TIMELINE_DDL = """
CREATE TABLE IF NOT EXISTS timeline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    event_type VARCHAR,
    title VARCHAR,
    description VARCHAR,
    icon VARCHAR,
    metadata TEXT,
    created_at TIMESTAMP
)
"""


@pytest.fixture(autouse=True)
def _db_limpo():
    Base.metadata.create_all(engine, tables=[WorkoutCompletion.__table__])
    with engine.begin() as conn:
        conn.exec_driver_sql(TIMELINE_DDL)
        conn.exec_driver_sql("DELETE FROM workout_completions")
        conn.exec_driver_sql("DELETE FROM timeline_events")
    yield


def _payload(**over):
    base = dict(idempotency_key="idem-chave-0001", workout_key="A",
                completed_date=date.today().isoformat())
    base.update(over)
    return base


def _post(payload=None, headers=H, cid=CLIENTE):
    return client.post(f"/workout-completions/{cid}", json=payload or _payload(), headers=headers)


def _conta(tabela, onde=""):
    with engine.begin() as conn:
        return conn.exec_driver_sql(f"SELECT COUNT(*) FROM {tabela} {onde}").scalar()


# ------------------------------------------------------------------ criação

def test_primeira_conclusao_cria_um_registro():
    r = _post()
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["created"] is True
    assert corpo["completion"]["workout_key"] == "A"
    assert corpo["completion"]["client_id"] == CLIENTE
    assert _conta("workout_completions") == 1


def test_conclusao_gera_exatamente_um_evento_de_timeline():
    _post()
    assert _conta("timeline_events", "WHERE event_type = 'workout'") == 1


def test_evento_de_timeline_carrega_a_relacao_com_a_conclusao():
    """Timeline é CONSEQUÊNCIA: precisa apontar para a conclusão que a originou."""
    corpo = _post().json()
    with engine.begin() as conn:
        meta = conn.exec_driver_sql(
            "SELECT metadata FROM timeline_events WHERE event_type='workout'"
        ).scalar()
    assert str(corpo["completion"]["id"]) in meta
    assert corpo["completion"]["idempotency_key"] in meta


# ------------------------------------------------------------- idempotência

def test_mesma_chave_repetida_devolve_o_registro_existente():
    primeira = _post().json()
    segunda = _post().json()
    assert segunda["created"] is False
    assert segunda["completion"]["id"] == primeira["completion"]["id"]
    assert _conta("workout_completions") == 1


def test_repeticao_nao_cria_segundo_evento_de_timeline():
    for _ in range(5):
        _post()
    assert _conta("workout_completions") == 1
    assert _conta("timeline_events", "WHERE event_type = 'workout'") == 1


def test_chave_perdida_nao_duplica_a_mesma_ocorrencia():
    """Storage limpo / outro aparelho: chave nova, mesma ocorrência real.

    Sem a chave natural, este caso duplicaria o treino silenciosamente.
    """
    _post()
    r = _post(_payload(idempotency_key="outra-chave-totalmente-diferente"))
    assert r.status_code == 200
    assert r.json()["created"] is False
    assert _conta("workout_completions") == 1


def test_treino_diferente_no_mesmo_dia_e_conclusao_propria():
    _post()
    r = _post(_payload(idempotency_key="idem-chave-0002", workout_key="B"))
    assert r.json()["created"] is True
    assert _conta("workout_completions") == 2


def test_mesmo_treino_em_dia_diferente_e_conclusao_propria():
    _post(_payload(completed_date="2026-08-10"))
    r = _post(_payload(idempotency_key="idem-chave-0003", completed_date="2026-08-11"))
    assert r.json()["created"] is True
    assert _conta("workout_completions") == 2


# --------------------------------------------------------------- corrida

def test_requisicoes_concorrentes_com_a_mesma_chave_nao_duplicam():
    """Duas tentativas simultâneas: uma cria, a outra reconhece. Nenhuma falha."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        respostas = [f.result() for f in [pool.submit(_post), pool.submit(_post)]]

    assert all(r.status_code == 200 for r in respostas), [r.text for r in respostas]
    criados = [r.json()["created"] for r in respostas]
    assert sorted(criados) == [False, True], f"esperava exatamente uma criação, veio {criados}"
    assert _conta("workout_completions") == 1
    assert _conta("timeline_events", "WHERE event_type = 'workout'") == 1


# ---------------------------------------------------------------- marcos

def test_marco_recebe_uma_unica_contribuicao_por_conclusao():
    """O contador conta CONCLUSÕES, não eventos — reenviar não infla."""
    for i in range(4):
        _post(_payload(idempotency_key=f"chave-marco-{i:04d}", workout_key=f"W{i}"))
    assert _conta("timeline_events", "WHERE event_type = 'achievement'") == 0

    # a quinta conclusão dispara o marco
    _post(_payload(idempotency_key="chave-marco-0004", workout_key="W4"))
    assert _conta("timeline_events", "WHERE event_type = 'achievement'") == 1

    # reenviar a MESMA quinta conclusão não pode disparar de novo
    for _ in range(3):
        _post(_payload(idempotency_key="chave-marco-0004", workout_key="W4"))
    assert _conta("timeline_events", "WHERE event_type = 'achievement'") == 1
    assert _conta("workout_completions") == 5


def test_marco_falso_nao_acontece_por_reenvio():
    """Regressão direta do risco do contrato antigo.

    Com POST /timeline/event, cinco reenvios da MESMA conclusão contariam como
    cinco treinos e disparariam o marco. Aqui não podem.
    """
    for _ in range(6):
        _post(_payload(idempotency_key="chave-unica-reenviada"))
    assert _conta("workout_completions") == 1
    assert _conta("timeline_events", "WHERE event_type = 'achievement'") == 0


# ------------------------------------------------------- atomicidade

def test_falha_no_meio_nao_deixa_registro_parcial(monkeypatch):
    """Se a Timeline falhar, a conclusão NÃO pode ficar gravada sozinha."""
    import routers.workout_completion as mod

    def explode(*a, **k):
        raise RuntimeError("falha simulada ao gravar o evento")

    monkeypatch.setattr(mod, "_inserir_evento", explode)
    r = _post()
    assert r.status_code == 500
    assert _conta("workout_completions") == 0
    assert _conta("timeline_events") == 0


# ------------------------------------------------------------- isolamento

def test_outro_cliente_nao_reutiliza_a_chave_de_ninguem():
    _post()
    r = client.post(f"/workout-completions/{OUTRO}", json=_payload(), headers=H_OUTRO)
    assert r.status_code == 403
    assert _conta("workout_completions") == 1


def test_cliente_nao_conclui_no_lugar_de_outro():
    r = client.post(f"/workout-completions/{OUTRO}", json=_payload(), headers=H)
    assert r.status_code == 403
    assert _conta("workout_completions") == 0


def test_sem_autenticacao_nao_registra():
    r = client.post(f"/workout-completions/{CLIENTE}", json=_payload())
    assert r.status_code in (401, 403)
    assert _conta("workout_completions") == 0


# ------------------------------------------------------------- leitura

def test_listagem_devolve_as_conclusoes_do_cliente():
    _post(_payload(completed_date="2026-08-10"))
    _post(_payload(idempotency_key="idem-chave-0009", workout_key="B",
                   completed_date="2026-08-12"))
    r = client.get(f"/workout-completions/{CLIENTE}", headers=H)
    assert r.status_code == 200
    assert {c["workout_key"] for c in r.json()} == {"A", "B"}


def test_listagem_filtra_por_data():
    _post(_payload(completed_date="2026-08-01"))
    _post(_payload(idempotency_key="idem-chave-0010", workout_key="B",
                   completed_date="2026-08-20"))
    r = client.get(f"/workout-completions/{CLIENTE}?since=2026-08-15", headers=H)
    assert [c["workout_key"] for c in r.json()] == ["B"]


def test_listagem_nao_vaza_conclusao_de_outro_cliente():
    _post()
    r = client.get(f"/workout-completions/{OUTRO}", headers=H)
    assert r.status_code == 403


# ------------------------------------------------- compatibilidade e legado

def test_plano_ausente_nao_impede_a_conclusao():
    """Sem plano ativo, `client_plan_id` = 0 e a chave natural continua válida.

    Cliente antigo / base sem `client_plans` não pode perder a conclusão.
    """
    corpo = _post().json()
    assert corpo["created"] is True
    assert corpo["completion"]["client_plan_id"] == 0


def test_data_ausente_assume_hoje():
    corpo = _post({"idempotency_key": "idem-sem-data-01", "workout_key": "A"}).json()
    assert corpo["completion"]["completed_date"] == date.today().isoformat()


def test_payload_invalido_e_recusado_sem_gravar():
    for ruim in [
        {"idempotency_key": "curta", "workout_key": "A"},          # < 8 chars
        {"idempotency_key": "chave-valida-123", "workout_key": ""},  # vazio
        {"workout_key": "A"},                                        # sem chave
    ]:
        r = _post(ruim)
        assert r.status_code == 422, ruim
    assert _conta("workout_completions") == 0


def test_timeline_antiga_nao_e_tocada():
    """O log legado é preservado: nada de apagar, reescrever ou fazer backfill."""
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO timeline_events (client_id, event_type, title, description, icon, metadata, created_at) "
            "VALUES (99, 'workout', 'Treino antigo', 'legado', '🏆', NULL, CURRENT_TIMESTAMP)"
        )
    _post()
    with engine.begin() as conn:
        antigo = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM timeline_events WHERE title = 'Treino antigo'"
        ).scalar()
    assert antigo == 1, "evento legado foi alterado ou removido"
    assert _conta("workout_completions") == 1


def test_restricao_unica_existe_no_schema():
    """A garantia é do BANCO, não só do código."""
    from models.workout_completion import UQ_OCORRENCIA

    nomes = {c.name for c in WorkoutCompletion.__table__.constraints if c.name}
    assert UQ_OCORRENCIA in nomes
    assert WorkoutCompletion.__table__.c.idempotency_key.unique is True


def test_corrida_real_cai_no_caminho_de_integrityerror(monkeypatch):
    """Prova DETERMINÍSTICA do tratamento de corrida.

    O teste com threads acima pode serializar no SQLite e passar sem nunca
    exercitar o `IntegrityError`. Aqui a corrida é forçada: a checagem inicial
    é cegada uma vez, então o INSERT encontra a linha que "outra requisição"
    gravou no meio do caminho. O endpoint precisa devolver a conclusão
    vencedora com 200 — nunca 500, nunca duplicata.
    """
    import routers.workout_completion as mod

    primeira = _post().json()
    assert primeira["created"] is True

    real = mod._existente
    estado = {"cegado": False}

    def cego_uma_vez(db, client_id, dados, dia):
        if not estado["cegado"]:
            estado["cegado"] = True
            return None  # finge que ainda não existe -> segue para o INSERT
        return real(db, client_id, dados, dia)

    monkeypatch.setattr(mod, "_existente", cego_uma_vez)

    r = _post()
    assert estado["cegado"] is True, "o caminho de corrida nao foi exercitado"
    assert r.status_code == 200, r.text
    assert r.json()["created"] is False
    assert r.json()["completion"]["id"] == primeira["completion"]["id"]
    assert _conta("workout_completions") == 1
    assert _conta("timeline_events", "WHERE event_type = 'workout'") == 1
