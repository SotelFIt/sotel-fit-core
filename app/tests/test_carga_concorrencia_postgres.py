"""
Concorrência do registro de carga em PostgreSQL — o banco de produção.

POR QUE ESTE MÓDULO EXISTE, SE JÁ HÁ TESTE DE CORRIDA EM SQLITE
---------------------------------------------------------------
O teste em SQLite (`test_exercise_set_log.py`) força o conflito injetando a
linha concorrente dentro do commit. Ele prova que o CÓDIGO reage certo a um
`IntegrityError` — e isso é útil —, mas não prova que duas transações paralelas
se comportam assim no banco que roda em produção. Em SQLite a escrita serializa
no arquivo: a disputa que se quer testar não chega a acontecer.

Em PostgreSQL ela acontece de verdade:

1. a transação perdedora **bloqueia** até o vencedor commitar, e só então
   recebe a violação de unicidade;
2. depois da violação a transação fica **abortada**: qualquer consulta antes do
   `rollback` falha com `InFailedSqlTransaction`;
3. o pool devolve conexões distintas às requisições paralelas, cada uma com sua
   própria transação.

Uma ressalva, para este arquivo não prometer mais do que entrega: testei
inverter a ordem `rollback -> reler` e a suíte SQLite **também** reprova. Não é
verdade que só o PostgreSQL pegue esse erro. O que só o PostgreSQL dá é a
disputa real — no SQLite o conflito precisa ser encenado, e uma encenação prova
que o código reage ao `IntegrityError`, não que duas transações paralelas o
produzam. A execução que acompanha este módulo registrou cinco violações de
unicidade legítimas no log do servidor, uma por rodada.

COMO RODAR
----------
Precisa de um PostgreSQL de teste. O módulo é PULADO quando não há um:

    set TEST_POSTGRES_URL=postgresql://user:senha@127.0.0.1:5434/base_de_teste
    pytest app/tests/test_carga_concorrencia_postgres.py

Nunca aponte para produção: o módulo CRIA e APAGA linhas do cliente fictício
abaixo, e derruba temporariamente a tabela `client_plans` para exercitar a
falha de consulta.
"""
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not URL,
    reason="defina TEST_POSTGRES_URL para rodar a concorrencia no banco de producao",
)

# Cliente fictício, fora de qualquer faixa real.
CLIENTE = 990001
DIA = "2026-10-03"
OCORRENCIA = "A#teste-concorrencia#0"


def _conectar():
    import psycopg2
    return psycopg2.connect(URL, connect_timeout=8)


@pytest.fixture()
def api():
    """Aplicação real ligada ao PostgreSQL de teste, com o cliente semeado."""
    os.environ["DATABASE_URL"] = URL
    os.environ["DATABASE_URL_SYNC"] = URL
    os.environ.setdefault("JWT_SECRET_KEY", "teste-concorrencia-sem-valor")
    os.environ.setdefault("LANDBOT_SECRET_TOKEN", "teste-concorrencia-admin")

    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from core.database import Base, engine
    from core.security import create_access_token
    import models  # noqa: F401
    from main import app

    Base.metadata.create_all(bind=engine)
    with engine.connect() as c:
        c.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_exercise_set_log_serie"
            " ON exercise_set_logs (client_id, client_plan_id, workout_key,"
            " occurrence_key, set_index, performed_date)"))
        c.execute(text("DELETE FROM exercise_set_logs WHERE client_id = :c"),
                  {"c": CLIENTE})
        c.execute(text("DELETE FROM client_plans WHERE client_id = :c"), {"c": CLIENTE})
        c.execute(text("DELETE FROM clients WHERE id = :c"), {"c": CLIENTE})
        c.execute(text(
            "INSERT INTO clients (id, name, email, phone, status, created_at)"
            " VALUES (:c, 'Teste Concorrencia', 'concorrencia@exemplo.invalid',"
            " '+5511900990001', 'active', CURRENT_TIMESTAMP)"), {"c": CLIENTE})
        c.execute(text(
            "INSERT INTO client_plans (client_id, content, status, created_at)"
            " VALUES (:c, 'plano de teste', 'active', CURRENT_TIMESTAMP)"),
            {"c": CLIENTE})
        c.commit()

    cliente = TestClient(app, raise_server_exceptions=False)
    token = {"Authorization": f"Bearer {create_access_token(CLIENTE)}"}
    yield cliente, token

    with engine.connect() as c:
        c.execute(text("DELETE FROM exercise_set_logs WHERE client_id = :c"),
                  {"c": CLIENTE})
        c.execute(text("DELETE FROM client_plans WHERE client_id = :c"), {"c": CLIENTE})
        c.execute(text("DELETE FROM clients WHERE id = :c"), {"c": CLIENTE})
        c.commit()


def _corpo(peso, serie=1):
    return {"workout_key": "A", "occurrence_key": OCORRENCIA,
            "exercise_name": "Teste", "set_index": serie,
            "performed_date": DIA, "weight_kg": peso}


def _linhas():
    c = _conectar()
    cur = c.cursor()
    cur.execute("SELECT set_index, weight_kg, client_plan_id FROM exercise_set_logs"
                " WHERE client_id = %s ORDER BY set_index", (CLIENTE,))
    r = cur.fetchall()
    c.close()
    return r


def _limpar():
    c = _conectar()
    c.autocommit = True
    c.cursor().execute("DELETE FROM exercise_set_logs WHERE client_id = %s", (CLIENTE,))
    c.close()


def test_duas_requisicoes_paralelas_nao_confirmam_valor_alheio(api):
    """O caso da revisão, no banco certo.

    Repetido algumas vezes porque a disputa é temporal: uma única rodada pode
    não sobrepor as transações, e um teste que só às vezes exercita o caminho
    não serve de prova.
    """
    cliente, token = api

    for _ in range(5):
        _limpar()
        barreira = threading.Barrier(2)
        saida = [None, None]

        def envia(peso, i):
            barreira.wait()
            r = cliente.put(f"/clients/{CLIENTE}/set-logs",
                            json=_corpo(peso), headers=token)
            saida[i] = (r.status_code, r.json().get("weight_kg") if r.status_code == 200 else None)

        ts = [threading.Thread(target=envia, args=(30.0, 0)),
              threading.Thread(target=envia, args=(34.5, 1))]
        for t in ts: t.start()
        for t in ts: t.join()

        linhas = _linhas()
        assert len(linhas) == 1, f"a identidade deixou de ser unica: {linhas}"

        for enviado, (status, devolvido) in zip((30.0, 34.5), saida):
            if status == 200:
                # A regra: um 200 descreve o que ESTA requisicao gravou. Outra
                # pode sobrescrever logo depois — isso e "ultimo escreve vence",
                # nao confirmacao falsa.
                assert devolvido == enviado, (
                    f"confirmou {devolvido} para quem enviou {enviado}")
            else:
                assert status in (409, 503), f"desfecho inesperado: {status}"

        assert linhas[0][1] in (30.0, 34.5), "o valor persistido nao e de nenhuma das duas"


def test_reenvio_paralelo_do_mesmo_valor_nao_duplica(api):
    cliente, token = api
    _limpar()
    barreira = threading.Barrier(4)

    def envia():
        barreira.wait()
        cliente.put(f"/clients/{CLIENTE}/set-logs", json=_corpo(34.5), headers=token)

    ts = [threading.Thread(target=envia) for _ in range(4)]
    for t in ts: t.start()
    for t in ts: t.join()

    linhas = _linhas()
    assert len(linhas) == 1, linhas
    assert linhas[0][1] == 34.5


def test_series_diferentes_em_paralelo_nao_se_atrapalham(api):
    """Sem conflito de identidade, o paralelismo precisa simplesmente funcionar.
    Sem este, bastaria serializar tudo para passar nos outros."""
    cliente, token = api
    _limpar()
    barreira = threading.Barrier(6)
    status = [None] * 6

    def envia(i):
        barreira.wait()
        r = cliente.put(f"/clients/{CLIENTE}/set-logs",
                        json=_corpo(20.0 + i, serie=i + 1), headers=token)
        status[i] = r.status_code

    ts = [threading.Thread(target=envia, args=(i,)) for i in range(6)]
    for t in ts: t.start()
    for t in ts: t.join()

    assert status == [200] * 6, status
    linhas = _linhas()
    assert len(linhas) == 6, linhas
    assert [l[1] for l in linhas] == [20.0, 21.0, 22.0, 23.0, 24.0, 25.0]


def test_falha_ao_consultar_o_plano_nao_grava_sob_plano_0(api):
    """A tabela do plano é derrubada de verdade, e o `client_plan_id` real não
    é 0 aqui — então gravar sob 0 seria visível e errado."""
    cliente, token = api
    _limpar()

    c = _conectar()
    c.autocommit = True
    c.cursor().execute("ALTER TABLE client_plans RENAME TO client_plans_fora")
    try:
        r = cliente.put(f"/clients/{CLIENTE}/set-logs",
                        json=_corpo(55.0), headers=token)
        assert r.status_code == 503, f"deu {r.status_code}"
        assert _linhas() == [], "gravou sem saber a que plano a carga pertence"
    finally:
        c.cursor().execute("ALTER TABLE client_plans_fora RENAME TO client_plans")
        c.close()

    r = cliente.put(f"/clients/{CLIENTE}/set-logs", json=_corpo(55.0), headers=token)
    assert r.status_code == 200, r.text
    linhas = _linhas()
    assert linhas and linhas[0][2] != 0, "voltou a gravar, mas sob plano 0"
