"""
Integracao com a Exercise API da YMove - demonstracao em video.

O fornecedor e SIMULADO aqui (nao ha credencial neste ambiente), mas o contrato
simulado foi tirado do openapi.json oficial, nao de suposicao:

  - `videoUrl`/`videoHlsUrl` sao pre-assinadas e expiram em 48h;
  - `excludeVideos=1` e browse mode e NAO consome cota;
  - o consumo tem DUAS dimensoes: minutos de video
    (`minutesUsed`/`minutesLimit`) e exercicios distintos em 30 dias
    (`monthlyExercisesUsed`/`monthlyExerciseLimit`, que pode vir "unlimited");
  - `thumbnailUrl` e estatico e nao expira, mas PODE NAO VIR em browse mode:
    "on Scale they are also returned without a video (...); on the capped
    plans they are not";
  - cota de exercicios estourada chega como 200 com `_warning`, sem os campos
    de video — nao como erro HTTP.

O que estes testes protegem, em uma frase cada:
  1. URL assinada nunca e persistida;
  2. abrir o treino nao chama o fornecedor;
  3. aluno so ve demonstracao do PROPRIO treino;
  4. aluno excluido nao passa;
  5. falha do fornecedor nao derruba a prescricao;
  6. a chave nunca sai do servidor.

O override de `get_db` e aplicado por TESTE e restaurado no fim: seis modulos
sobrescrevem essa dependencia no import e o ultimo importado ganha.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault("JWT_SECRET_KEY", "ec/hBUFhntuNSkRbbVvo6CnWDOkXV2b8TMLI5vMcFd8=")
os.environ.setdefault("LANDBOT_SECRET_TOKEN", "token-admin-teste")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
# Credencial FICTICIA, so para o modulo se considerar configurado. Nenhuma
# chamada real sai daqui: `requests.get` e substituido em cada teste.
os.environ["YMOVE_API_KEY"] = "chave-de-teste-sem-valor-real"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
import core.security as seguranca
from core.security import create_access_token
from models.exercise import Exercise
from main import app
from services import ymove

# Token lido do MODULO, nao do ambiente.
#
# `core/security.py` captura LANDBOT_SECRET_TOKEN uma vez, no import, numa
# constante de modulo — e e com ela que a comparacao acontece. No ambiente,
# porem, o valor muda: `conftest.py` ATRIBUI um valor e `test_full_flow.py`
# atribui outro, enquanto este modulo usa `setdefault`, que entao nao faz nada.
# Resultado: isolado o modulo passa, e na suite completa o header levava um
# token e o app comparava com outro — 401 em tudo que e rota de admin.
#
# Ler do modulo torna o teste indiferente a ordem de import, que e a causa.
ADMIN = {"x-api-key": seguranca.LANDBOT_SECRET_TOKEN}
ALUNO = {"Authorization": f"Bearer {create_access_token(1)}"}
OUTRO_ALUNO = {"Authorization": f"Bearer {create_access_token(2)}"}

YM_ID = "11111111-2222-3333-4444-555555555555"
URL_ASSINADA = (
    "https://cdn.ymove.app/v/leg-extension.mp4"
    "?X-Amz-Signature=abc123&X-Amz-Expires=172800"
)
THUMB = "https://ymove.app/thumbs/leg-extension-default.jpg"

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


class RespostaFalsa:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


class FornecedorSimulado:
    """Registra TODA chamada: e assim que se prova que nao houve consumo."""

    def __init__(self):
        self.chamadas = []
        self.erro = None
        self.status = 200
        # Plano COM capa em browse mode (equivalente a Scale). Os testes que
        # exercitam o plano com limite de exercicios desligam isto.
        self.capa_em_browse = True
        # Cota de exercicios distintos estourada: o fornecedor responde 200,
        # remove os campos de video e explica em `_warning`.
        self.cota_estourada = False
        # `monthlyExerciseLimit` vem como a string "unlimited" em plano anual.
        self.limite_de_exercicios = 50

    def get(self, url, params=None, headers=None, timeout=None):
        self.chamadas.append({"url": url, "params": dict(params or {}),
                              "headers": dict(headers or {})})
        if self.erro:
            raise self.erro
        if self.status != 200:
            return RespostaFalsa({"error": "...", "retryAfterMs": 3000}, self.status)

        if url.endswith("/usage"):
            return RespostaFalsa({"data": {
                "plan": "starter", "status": "active",
                "minutesUsed": 12, "minutesLimit": 600, "minutesRemaining": 588,
                "percentUsed": 2,
                "monthlyExercisesUsed": 3,
                "monthlyExerciseLimit": self.limite_de_exercicios,
                "rateLimit": 60, "trialEndsAt": None,
                "whiteVideoAccess": True, "premiumVideoAccess": False,
                "postureAnalyses": {"used": 1, "included": 10},
            }})

        navegando = str((params or {}).get("excludeVideos")) in ("1", "True", "true")
        exercicio = {
            "id": YM_ID, "slug": "leg-extension", "title": "Leg Extension",
            "muscleGroup": "quads", "equipment": "machine", "difficulty": "beginner",
            "hasVideo": True, "hasVideoWhite": True, "hasVideoGym": False,
            "videoDurationSecs": 11,
            # Enum do contrato e minusculo.
            # DUAS variantes, como no catalogo real: e entre elas que o
            # treinador escolhe, e e por existirem duas que a queda silenciosa
            # para a principal e perigosa.
            "videos": [
                {"tag": "gym", "orientation": "portrait", "isPrimary": True},
                {"tag": "fundo-branco", "orientation": "portrait", "isPrimary": False},
            ],
        }
        # A capa acompanha o VIDEO. Em browse mode ela so vem nos planos sem
        # limite de exercicios — por isso ela e colocada aqui, condicionalmente,
        # e nao no literal acima.
        if not navegando or self.capa_em_browse:
            exercicio["thumbnailUrl"] = THUMB
            for _v in exercicio["videos"]:
                _v["thumbnailUrl"] = THUMB

        corpo_extra = {}
        if not navegando:
            if self.cota_estourada:
                # Contrato do MonthlyCapWarning: os campos de video sao
                # REMOVIDOS e o motivo vem no aviso. Status continua 200.
                corpo_extra["_warning"] = {
                    "message": "monthly exercise cap exceeded",
                    "reason": "monthly_exercise_cap",
                    "monthlyExercisesUsed": 50, "monthlyExerciseLimit": 50,
                    "upgradeUrl": "https://ymove.app/upgrade",
                }
            else:
                # Browse mode NAO devolve estas; o contrato e explicito.
                exercicio["videoUrl"] = URL_ASSINADA
                for _v in exercicio["videos"]:
                    _v["videoUrl"] = URL_ASSINADA

        if "/exercises/" in url:
            return RespostaFalsa({"data": exercicio, **corpo_extra})
        return RespostaFalsa({"data": [exercicio],
                              "pagination": {"page": 1, "pageSize": 20,
                                             "total": 1, "totalPages": 1},
                              **corpo_extra})

    # --- leitura dos registros -------------------------------------------
    @property
    def pediu_video(self):
        """Houve chamada que CONSOME cota (sem excludeVideos)?"""
        return any(
            "/exercises" in c["url"]
            and str(c["params"].get("excludeVideos")) not in ("1", "True", "true")
            for c in self.chamadas
        )


@pytest.fixture(autouse=True)
def _base(monkeypatch):
    anterior = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db

    Base.metadata.create_all(engine, tables=[Exercise.__table__])
    with engine.begin() as c:
        c.exec_driver_sql("""CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY, name TEXT, deleted_at TIMESTAMP)""")
        c.exec_driver_sql("""CREATE TABLE IF NOT EXISTS client_plans (
            id INTEGER PRIMARY KEY, client_id INTEGER, status TEXT,
            enrichment_json TEXT, created_at TIMESTAMP)""")
        for t in ("exercises", "clients", "client_plans"):
            c.exec_driver_sql(f"DELETE FROM {t}")
        c.exec_driver_sql(
            "INSERT INTO clients (id,name,deleted_at) VALUES "
            "(1,'Ana',NULL),(2,'Bruno',NULL),(3,'Excluida',CURRENT_TIMESTAMP)")
        enr = json.dumps({"exercises": [
            {"name_raw": "Cadeira Extensora", "library_ref": "cadeira-extensora",
             "status": "resolved"},
            {"name_raw": "Aquecimento Cardio", "library_ref": None,
             "status": "unresolved"},
        ]})
        # Ana tem o exercicio no plano; Bruno nao tem plano nenhum.
        c.exec_driver_sql(
            "INSERT INTO client_plans (client_id,status,enrichment_json,created_at) "
            "VALUES (1,'active',?,CURRENT_TIMESTAMP)", (enr,))

    db = TestingSessionLocal()
    db.add(Exercise(
        slug="cadeira-extensora", name="Cadeira Extensora", aliases=["Leg Extension"],
        primary_muscle="quadriceps", secondary_muscles=[], equipment="maquina",
        level="iniciante", common_errors=[], cautions=[],
        approved_substitutions=[], media=[], is_active=True))
    db.add(Exercise(
        slug="supino-reto", name="Supino Reto", aliases=[], primary_muscle="peito",
        secondary_muscles=[], equipment="barra", level="iniciante",
        common_errors=[], cautions=[], approved_substitutions=[], media=[],
        is_active=True))
    db.commit()
    db.close()

    fake = FornecedorSimulado()
    monkeypatch.setattr(ymove.requests, "get", fake.get)
    yield fake

    if anterior is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = anterior


def _vincular():
    return client.put(
        "/admin/exercises/cadeira-extensora/ymove",
        json={"provider": "ymove", "exercise_id": YM_ID, "slug": "leg-extension",
              "title": "Leg Extension", "variant": "gym", "thumbnail_url": THUMB,
              "orientation": "portrait", "duration_secs": 11},
        headers=ADMIN,
    )


def _guardado(slug="cadeira-extensora"):
    with engine.begin() as c:
        linha = c.exec_driver_sql(
            f"SELECT external_demo FROM exercises WHERE slug = '{slug}'").fetchone()
    bruto = linha[0]
    if bruto in (None, ""):
        return None
    return json.loads(bruto) if isinstance(bruto, str) else bruto


# ===================================================== vinculo e persistencia

def test_admin_vincula_e_a_referencia_fica_guardada():
    r = _vincular()
    assert r.status_code == 200, r.text
    guardado = _guardado()
    assert guardado["provider"] == "ymove"
    assert guardado["exercise_id"] == YM_ID
    assert guardado["variant"] == "gym"


def test_NENHUMA_url_assinada_e_persistida():
    """O coracao da integracao: a URL morre em 48h. Guardar e criar link morto."""
    _vincular()
    bruto = json.dumps(_guardado())
    for marca in ("X-Amz-Signature", "X-Amz-Expires", "cdn.ymove.app", ".mp4"):
        assert marca not in bruto, f"URL assinada vazou para o banco: {marca}"


def test_o_slug_local_continua_sendo_a_identidade():
    """O vinculo aponta para o fornecedor; nao substitui o nosso exercicio."""
    _vincular()
    with engine.begin() as c:
        linha = c.exec_driver_sql(
            "SELECT slug, name FROM exercises WHERE slug='cadeira-extensora'").fetchone()
    assert linha == ("cadeira-extensora", "Cadeira Extensora")


def test_vinculo_com_thumbnail_de_outro_dominio_e_recusado():
    r = client.put("/admin/exercises/cadeira-extensora/ymove",
                   json={"provider": "ymove", "exercise_id": YM_ID,
                         "thumbnail_url": "https://cdn.evil.example/x.jpg"},
                   headers=ADMIN)
    assert r.status_code == 422
    assert _guardado() is None


def test_vinculo_com_url_assinada_disfarcada_e_recusado():
    r = client.put("/admin/exercises/cadeira-extensora/ymove",
                   json={"provider": "ymove", "exercise_id": YM_ID,
                         "thumbnail_url": THUMB + "?X-Amz-Signature=abc"},
                   headers=ADMIN)
    assert r.status_code == 422


def test_desvincular_nao_toca_no_exercicio():
    _vincular()
    r = client.delete("/admin/exercises/cadeira-extensora/ymove", headers=ADMIN)
    assert r.status_code == 200
    assert _guardado() is None
    with engine.begin() as c:
        assert c.exec_driver_sql(
            "SELECT count(*) FROM exercises WHERE slug='cadeira-extensora'"
        ).fetchone()[0] == 1


def test_somente_admin_vincula_ou_desvincula():
    assert _vincular().status_code == 200
    assert client.put("/admin/exercises/cadeira-extensora/ymove",
                      json={"provider": "ymove", "exercise_id": YM_ID},
                      headers=ALUNO).status_code == 403
    assert client.delete("/admin/exercises/cadeira-extensora/ymove",
                         headers=ALUNO).status_code == 403


# ============================================================ consumo de cota

def test_busca_do_admin_NAO_consome_cota(_base):
    """Browse mode: `excludeVideos=1` em toda chamada de navegacao."""
    r = client.get("/admin/exercises/ymove/buscar?q=leg", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["itens"][0]["title"] == "Leg Extension"
    assert not _base.pediu_video, "a navegacao do admin nao pode pedir video"
    assert all(str(c["params"].get("excludeVideos")) == "1" for c in _base.chamadas)


def test_busca_nao_devolve_url_de_video(_base):
    r = client.get("/admin/exercises/ymove/buscar?q=leg", headers=ADMIN)
    assert "videoUrl" not in r.text and "X-Amz" not in r.text


def test_abrir_o_exercicio_NAO_chama_o_fornecedor(_base):
    """A tela do treino carrega a orientacao por aqui. Se esta rota pedisse
    video, abrir o treino queimaria cota de todo exercicio da sessao."""
    _vincular()
    _base.chamadas.clear()
    r = client.get("/exercises/cadeira-extensora", headers=ALUNO)
    assert r.status_code == 200
    assert _base.chamadas == [], "abrir o exercicio nao pode chamar o fornecedor"


def test_uso_e_lido_do_fornecedor_para_o_admin(_base):
    r = client.get("/admin/exercises/ymove/uso", headers=ADMIN)
    assert r.status_code == 200
    d = r.json()
    assert d["exercicios_distintos_no_mes"] == 3
    assert d["exercicios_limite"] == 50
    assert d["plano"] == "starter"


def test_aluno_nao_enxerga_a_rota_de_uso():
    assert client.get("/admin/exercises/ymove/uso", headers=ALUNO).status_code == 403


# ====================================================== demonstracao do aluno

def test_aluno_recebe_url_fresca_so_quando_pede(_base):
    _vincular()
    _base.chamadas.clear()
    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.status_code == 200, r.text
    assert r.json()["url"] == URL_ASSINADA
    assert r.json()["expira_em_horas"] == 48
    assert _base.pediu_video, "a demonstracao precisa pedir o video"


def test_a_previa_usa_o_thumbnail_guardado(_base):
    """Thumbnail e estatico: pode ser guardado e nao custa cota."""
    _vincular()
    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.json()["thumbnail"] == THUMB


def test_aluno_de_OUTRO_treino_e_recusado():
    """Sem isto, qualquer aluno autenticado viraria proxy do catalogo inteiro."""
    _vincular()
    r = client.get("/exercises/cadeira-extensora/demo", headers=OUTRO_ALUNO)
    assert r.status_code == 403


def test_exercicio_fora_do_plano_do_aluno_e_recusado():
    client.put("/admin/exercises/supino-reto/ymove",
               json={"provider": "ymove", "exercise_id": YM_ID}, headers=ADMIN)
    r = client.get("/exercises/supino-reto/demo", headers=ALUNO)
    assert r.status_code == 403


def test_aluno_EXCLUIDO_nao_recebe_demonstracao():
    _vincular()
    excluida = {"Authorization": f"Bearer {create_access_token(3)}"}
    assert client.get("/exercises/cadeira-extensora/demo",
                      headers=excluida).status_code == 401


def test_sem_autenticacao_nao_ha_demonstracao():
    _vincular()
    assert client.get("/exercises/cadeira-extensora/demo").status_code == 401


def test_exercicio_sem_vinculo_responde_404():
    assert client.get("/exercises/supino-reto/demo", headers=ADMIN).status_code == 404


def test_nao_existe_proxy_para_id_arbitrario(_base):
    """A rota recebe o SLUG LOCAL. O id do fornecedor sai do vinculo aprovado -
    o aluno nao consegue apontar para um exercicio qualquer do catalogo."""
    r = client.get(f"/exercises/{YM_ID}/demo", headers=ALUNO)
    assert r.status_code == 404
    assert _base.chamadas == []


# ========================================= falha do fornecedor nao derruba nada

def test_limite_atingido_vira_429_controlado(_base):
    _vincular()
    _base.status = 429
    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.status_code == 429
    assert "limite" in r.json()["detail"]


def test_credencial_recusada_nao_vaza_detalhe(_base):
    _vincular()
    _base.status = 401
    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.status_code == 503
    assert "chave" not in r.text.lower() and "key" not in r.text.lower()


def test_fornecedor_fora_do_ar_vira_503(_base):
    import requests as _rq
    _vincular()
    _base.erro = _rq.Timeout("timeout")
    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.status_code == 503


def test_a_prescricao_continua_de_pe_quando_o_video_falha(_base):
    """O aluno precisa conseguir treinar mesmo sem demonstracao."""
    import requests as _rq
    _vincular()
    _base.erro = _rq.Timeout("timeout")
    assert client.get("/exercises/cadeira-extensora/demo", headers=ALUNO).status_code == 503
    _base.erro = None
    r = client.get("/exercises/cadeira-extensora", headers=ALUNO)
    assert r.status_code == 200
    assert r.json()["name"] == "Cadeira Extensora"


# ===================================================== credencial e cobertura

def test_a_chave_vai_em_HEADER_e_nunca_em_query(_base):
    client.get("/admin/exercises/ymove/buscar?q=leg", headers=ADMIN)
    for c in _base.chamadas:
        assert c["headers"].get("X-API-Key") == os.environ["YMOVE_API_KEY"]
        assert "api_key" not in c["params"], "chave em query string vaza em log de proxy"
        assert "api_key" not in c["url"]


def test_a_chave_nunca_aparece_na_resposta(_base):
    _vincular()
    for r in (client.get("/admin/exercises/ymove/buscar?q=leg", headers=ADMIN),
              client.get("/admin/exercises/ymove/uso", headers=ADMIN),
              client.get("/exercises/cadeira-extensora/demo", headers=ALUNO),
              client.get("/exercises/cadeira-extensora", headers=ALUNO)):
        assert os.environ["YMOVE_API_KEY"] not in r.text


def test_cobertura_conta_so_o_que_esta_prescrito():
    _vincular()
    r = client.get("/admin/exercises/ymove/cobertura", headers=ADMIN)
    assert r.status_code == 200
    d = r.json()
    assert d["ocorrencias_totais"] == 1
    assert d["ocorrencias_com_demonstracao"] == 1
    assert d["com_demonstracao"] == [{"slug": "cadeira-extensora", "ocorrencias": 1}]
    assert d["fila_de_revisao"] == []
    # Nome que nao resolve para a Biblioteca e outra fila, nao candidato a video.
    assert d["sem_correspondencia_na_biblioteca"] == [
        {"nome": "Aquecimento Cardio", "ocorrencias": 1}]


def test_fila_de_revisao_mostra_o_que_falta():
    r = client.get("/admin/exercises/ymove/cobertura", headers=ADMIN)
    d = r.json()
    assert d["ocorrencias_com_demonstracao"] == 0
    assert d["fila_de_revisao"] == [{"slug": "cadeira-extensora", "ocorrencias": 1}]


def test_sem_credencial_a_integracao_fica_indisponivel_sem_quebrar(monkeypatch):
    monkeypatch.delenv("YMOVE_API_KEY", raising=False)
    assert client.get("/admin/exercises/ymove/buscar?q=x",
                      headers=ADMIN).status_code == 503
    assert client.get("/admin/exercises/ymove/uso", headers=ADMIN).status_code == 503
    # E o exercicio continua abrindo normalmente.
    assert client.get("/exercises/cadeira-extensora", headers=ALUNO).status_code == 200


# =========================================================================
# PREMISSAS CORRIGIDAS CONTRA O openapi.json (v2.5.0)
#
# Duas coisas que a primeira versao desta integracao assumiu errado, e que o
# contrato do fornecedor contradiz textualmente. Cada uma custa de um jeito
# diferente se voltar: a primeira esconde exercicios vinculaveis da tela do
# admin; a segunda mostra ao Proprietario metade do consumo que ele paga.
# =========================================================================

# ------------------------------------------- 1) capa pode faltar em browse

def test_busca_funciona_sem_capa_no_plano_com_limite(_base):
    """Contrato do objeto Thumbnails: "on the capped plans they are not"
    devolvidas em browse mode. A busca NAO pode depender da figura."""
    _base.capa_em_browse = False
    r = client.get("/admin/exercises/ymove/buscar?q=leg", headers=ADMIN)
    assert r.status_code == 200, r.text
    item = r.json()["itens"][0]
    assert item["thumbnail_url"] is None, "o simulado precisa estar sem capa aqui"
    # O que sustenta a decisao humana continua inteiro sem a imagem:
    assert item["title"] == "Leg Extension"
    assert item["equipment"] == "machine"
    assert item["muscle_group"] == "quads"
    assert item["variantes"][0]["tag"] == "gym"
    assert not _base.pediu_video, "faltar capa nao autoriza pedir video"


def test_vinculo_sem_capa_e_salvo(_base):
    """Exigir thumbnail recusaria um vinculo correto no plano com limite."""
    r = client.put(
        "/admin/exercises/cadeira-extensora/ymove",
        json={"provider": "ymove", "exercise_id": YM_ID, "slug": "leg-extension",
              "title": "Leg Extension", "variant": "gym", "duration_secs": 11},
        headers=ADMIN,
    )
    assert r.status_code == 200, r.text
    guardado = _guardado()
    assert guardado["exercise_id"] == YM_ID
    assert "thumbnail_url" not in guardado or guardado["thumbnail_url"] is None


def test_treino_abre_e_demonstra_sem_capa(_base):
    """Sem capa o aluno perde a previa, nao a demonstracao."""
    _base.capa_em_browse = False
    client.put(
        "/admin/exercises/cadeira-extensora/ymove",
        json={"provider": "ymove", "exercise_id": YM_ID, "slug": "leg-extension",
              "variant": "gym"},
        headers=ADMIN,
    )
    assert client.get("/exercises/cadeira-extensora", headers=ALUNO).status_code == 200

    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.status_code == 200, r.text
    assert r.json()["url"] == URL_ASSINADA, "o video nao depende da capa"


def test_nenhuma_chamada_pede_video_para_conseguir_capa(_base):
    """A tentacao obvia: "sem capa, pede o video que ele traz a capa".
    Isso consome cota por exercicio que ninguem assistiu."""
    _base.capa_em_browse = False
    client.get("/admin/exercises/ymove/buscar?q=leg", headers=ADMIN)
    client.get("/admin/exercises/ymove/buscar?q=cadeira", headers=ADMIN)
    assert not _base.pediu_video
    assert all(str(c["params"].get("excludeVideos")) == "1"
               for c in _base.chamadas if "/exercises" in c["url"])


# --------------------------------------- 2) consumo tem DUAS dimensoes

def test_uso_apresenta_minutos_E_exercicios_distintos(_base):
    """As duas dimensoes que o fornecedor publica, lado a lado.

    Mostrar so uma delas daria ao Proprietario a impressao de folga que ele
    pode nao ter: da para estar longe do limite de exercicios distintos e
    perto do limite de minutos, que e o que a pagina de precos vende.
    """
    d = client.get("/admin/exercises/ymove/uso", headers=ADMIN).json()

    # dimensao 1 - minutos
    assert d["minutos_usados"] == 12
    assert d["minutos_limite"] == 600
    assert d["minutos_restantes"] == 588
    assert d["minutos_percentual"] == 2

    # dimensao 2 - exercicios distintos
    assert d["exercicios_distintos_no_mes"] == 3
    assert d["exercicios_limite"] == 50
    assert d["exercicios_restantes"] == 47
    assert d["exercicios_ilimitados"] is False

    assert d["requisicoes_por_minuto"] == 60


def test_limite_unlimited_nao_vira_numero_inventado(_base):
    """`monthlyExerciseLimit` vem como a string "unlimited" em plano anual.
    Subtrair de uma palavra ou tratar como 0 produziria numero falso."""
    _base.limite_de_exercicios = "unlimited"
    d = client.get("/admin/exercises/ymove/uso", headers=ADMIN).json()
    assert d["exercicios_limite"] == "unlimited"
    assert d["exercicios_ilimitados"] is True
    assert d["exercicios_restantes"] is None
    # Minutos continuam medidos mesmo com exercicios ilimitados.
    assert d["minutos_limite"] == 600


def test_uso_nao_inventa_numero_que_o_fornecedor_nao_mandou(_base):
    """Nenhum campo e preenchido por estimativa nossa."""
    d = client.get("/admin/exercises/ymove/uso", headers=ADMIN).json()
    assert d["plano"] == "starter"
    assert d["video_sem_marca"] is False, "plano starter tem marca Your Move"
    assert d["video_fundo_branco"] is True
    assert d["fim_do_teste"] is None


# ------------------------- cota estourada chega como 200, nao como erro HTTP

def test_cota_estourada_nao_e_confundida_com_ausencia_de_video(_base):
    """O fornecedor responde 200 e REMOVE os campos de video, explicando em
    `_warning`. Sem ler o aviso, a tela diria ao aluno que o exercicio nao tem
    demonstracao — quando o problema e da conta, e tem solucao."""
    _vincular()
    _base.cota_estourada = True
    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.status_code == 429, f"deu {r.status_code}: {r.text}"
    assert "404" not in str(r.status_code)
    assert "limite" in r.json()["detail"].lower()


def test_cota_estourada_nao_apaga_o_vinculo_nem_o_exercicio(_base):
    """Limite e do mes, nao do cadastro: nada e desfeito por causa dele."""
    _vincular()
    _base.cota_estourada = True
    client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)

    assert _guardado()["exercise_id"] == YM_ID, "o vinculo nao pode ser perdido"
    r = client.get("/exercises/cadeira-extensora", headers=ALUNO)
    assert r.status_code == 200, "o treino continua aberto com a cota estourada"


def test_sem_video_de_verdade_continua_sendo_404(_base):
    """O contrario do teste acima: quando NAO ha aviso de cota e tambem nao ha
    video, a resposta honesta e 404 — nao 429. Sem esta, bastaria mapear tudo
    para 429 e a distincao morreria."""
    _vincular()
    sem_video = {"id": YM_ID, "slug": "leg-extension", "title": "Leg Extension",
                 "muscleGroup": "quads", "equipment": "machine",
                 "hasVideo": False, "videos": []}
    _base_get = _base.get

    def get(url, **kw):
        _base_get(url, **kw)
        if "/exercises/" in url:
            return RespostaFalsa({"data": sem_video})
        return RespostaFalsa({"data": [sem_video], "pagination": {}})

    import services.ymove as _ym
    _ym.requests.get = get
    try:
        r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    finally:
        _ym.requests.get = _base_get
    assert r.status_code == 404, f"deu {r.status_code}: {r.text}"


# =========================================================================
# VARIANTE VINCULADA E VINCULATIVA
#
# As variantes sao filmagens diferentes do MESMO movimento: "academia" e
# "fundo branco" tem cenario, enquadramento e as vezes orientacao propria. O
# treinador escolhe entre elas na tela de vinculo, com as duas a vista.
#
# Entregar outra em silencio desfaz essa escolha sem avisar ninguem: o vinculo
# continua dizendo uma coisa e o aluno assiste outra. Estes testes existem para
# que essa queda nunca volte por conveniencia.
# =========================================================================

def _so_academia(_base):
    """O fornecedor passa a oferecer SO a variante de academia."""
    original = _base.get

    def get(url, params=None, headers=None, timeout=None):
        r = original(url, params=params, headers=headers, timeout=timeout)
        corpo = r.json()
        dados = corpo.get("data")
        alvo = dados if isinstance(dados, dict) else (dados or [{}])[0]
        alvo["videos"] = [v for v in alvo.get("videos", []) if v.get("tag") == "gym"]
        return RespostaFalsa(corpo, r.status_code)

    return get


def test_variante_vinculada_ausente_NAO_cai_para_outra(_base, monkeypatch):
    """O caso que o Proprietario pediu para cobrir: a variante escolhida sumiu
    e OUTRA esta disponivel. A resposta e indisponibilidade, nao a outra."""
    client.put(
        "/admin/exercises/cadeira-extensora/ymove",
        json={"provider": "ymove", "exercise_id": YM_ID, "slug": "leg-extension",
              "title": "Leg Extension", "variant": "fundo-branco"},
        headers=ADMIN,
    )
    monkeypatch.setattr(ymove.requests, "get", _so_academia(_base))

    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.status_code == 404, f"deu {r.status_code}: {r.text}"
    assert URL_ASSINADA not in r.text, "entregou o video da OUTRA variante"


def test_variante_ausente_nao_altera_o_vinculo(_base, monkeypatch):
    """Indisponibilidade e do momento. O vinculo que um humano aprovou nao e
    desfeito por causa dela — quem revisa o vinculo e o treinador."""
    client.put(
        "/admin/exercises/cadeira-extensora/ymove",
        json={"provider": "ymove", "exercise_id": YM_ID, "slug": "leg-extension",
              "variant": "fundo-branco"},
        headers=ADMIN,
    )
    monkeypatch.setattr(ymove.requests, "get", _so_academia(_base))
    client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)

    assert _guardado()["variant"] == "fundo-branco", "o vinculo foi alterado"


def test_variante_ausente_nao_derruba_a_prescricao(_base, monkeypatch):
    client.put(
        "/admin/exercises/cadeira-extensora/ymove",
        json={"provider": "ymove", "exercise_id": YM_ID, "slug": "leg-extension",
              "variant": "fundo-branco"},
        headers=ADMIN,
    )
    monkeypatch.setattr(ymove.requests, "get", _so_academia(_base))
    client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)

    r = client.get("/exercises/cadeira-extensora", headers=ALUNO)
    assert r.status_code == 200, "o exercicio parou de abrir"


def test_variante_vinculada_presente_e_a_que_toca(_base):
    """O outro lado da mesma regra: pedida a que existe, e ela que vem."""
    _vincular()  # variant = "gym"
    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.status_code == 200, r.text
    assert r.json()["url"] == URL_ASSINADA


def test_sem_variante_vinculada_a_principal_continua_valendo(_base):
    """Sem escolha humana registrada nao ha o que respeitar: a principal serve.
    Sem esta, a correcao viraria "exige variante para tudo"."""
    client.put(
        "/admin/exercises/cadeira-extensora/ymove",
        json={"provider": "ymove", "exercise_id": YM_ID, "slug": "leg-extension"},
        headers=ADMIN,
    )
    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.status_code == 200, r.text
    assert r.json()["url"] == URL_ASSINADA


def test_variante_ausente_E_cota_estourada_relata_a_COTA(_base, monkeypatch):
    """A distincao que custa: com a cota estourada o fornecedor remove os
    campos de video de TODAS as variantes. Se a checagem da variante viesse
    primeiro, "cota acabou" seria relatado como "variante sumiu" — e o
    treinador iria procurar o vinculo errado em vez de olhar a conta."""
    client.put(
        "/admin/exercises/cadeira-extensora/ymove",
        json={"provider": "ymove", "exercise_id": YM_ID, "slug": "leg-extension",
              "variant": "fundo-branco"},
        headers=ADMIN,
    )
    _base.cota_estourada = True
    monkeypatch.setattr(ymove.requests, "get", _so_academia(_base))

    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.status_code == 429, f"deu {r.status_code}: {r.text}"


def test_variante_sem_url_e_tratada_como_ausente(_base, monkeypatch):
    """A variante existe na lista mas vem sem `videoUrl`. Sem cota estourada,
    isso e indisponibilidade dela — e nao autoriza pegar a do vizinho."""
    original = _base.get

    def get(url, params=None, headers=None, timeout=None):
        r = original(url, params=params, headers=headers, timeout=timeout)
        corpo = r.json()
        dados = corpo.get("data")
        alvo = dados if isinstance(dados, dict) else (dados or [{}])[0]
        for v in alvo.get("videos", []):
            if v.get("tag") == "fundo-branco":
                v.pop("videoUrl", None)
        return RespostaFalsa(corpo, r.status_code)

    client.put(
        "/admin/exercises/cadeira-extensora/ymove",
        json={"provider": "ymove", "exercise_id": YM_ID, "slug": "leg-extension",
              "variant": "fundo-branco"},
        headers=ADMIN,
    )
    monkeypatch.setattr(ymove.requests, "get", get)

    r = client.get("/exercises/cadeira-extensora/demo", headers=ALUNO)
    assert r.status_code == 404
    assert URL_ASSINADA not in r.text, "usou o video de outra variante"
