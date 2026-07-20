"""
LIB-003 - testes da API da Biblioteca de Exercicios V1.

Isolamento: SQLite in-memory, com override de get_db no app REAL (main.app), para
cobrir tambem regressao de rotas existentes. DATABASE_URL e forcado para sqlite
ANTES de importar main (o .env default aponta para postgresql+asyncpg, que nao
existe neste ambiente de teste - mesma causa da falha historica de test_full_flow).

Auth (convencao real do backend):
  - admin  -> header x-api-key = LANDBOT_SECRET_TOKEN (verify_dual_auth -> 0)
  - cliente -> Bearer JWT de acesso (create_access_token(client_id))
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault("JWT_SECRET_KEY", "ec/hBUFhntuNSkRbbVvo6CnWDOkXV2b8TMLI5vMcFd8=")
os.environ.setdefault("LANDBOT_SECRET_TOKEN", "token-admin-teste")
# Impede o import de main de instanciar o engine asyncpg do .env.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from core.security import create_access_token
from models.exercise import Exercise  # noqa: F401  (registra a tabela no metadata)
from main import app

ADMIN_TOKEN = os.environ["LANDBOT_SECRET_TOKEN"]
ADMIN_HEADERS = {"x-api-key": ADMIN_TOKEN}
CLIENT_HEADERS = {"Authorization": f"Bearer {create_access_token(99)}"}

# Engine unico in-memory compartilhado por toda a suite.
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


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_db():
    Base.metadata.create_all(engine, tables=[Exercise.__table__])
    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM exercises")
    yield


def _payload(**over):
    base = dict(
        slug="supino-reto", name="Supino reto", primary_muscle="Peito",
        equipment="Barra", level="iniciante",
    )
    base.update(over)
    return base


def _create(as_admin=True, **over):
    headers = ADMIN_HEADERS if as_admin else CLIENT_HEADERS
    return client.post("/admin/exercises", json=_payload(**over), headers=headers)


# ---------------- autenticacao ----------------

def test_listagem_exige_autenticacao():
    r = client.get("/exercises")
    assert r.status_code == 401


def test_detalhe_exige_autenticacao():
    r = client.get("/exercises/supino-reto")
    assert r.status_code == 401


def test_cliente_autenticado_le_listagem():
    _create()
    r = client.get("/exercises", headers=CLIENT_HEADERS)
    assert r.status_code == 200
    assert len(r.json()) == 1


# ---------------- autorizacao administrativa ----------------

def test_cliente_nao_pode_criar():
    r = _create(as_admin=False)
    assert r.status_code == 403


def test_criacao_sem_auth_rejeitada():
    r = client.post("/admin/exercises", json=_payload())
    assert r.status_code == 401


def test_admin_pode_criar():
    r = _create()
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slug"] == "supino-reto"
    assert body["is_active"] is True
    assert body["secondary_muscles"] == []


# ---------------- criacao / validacoes ----------------

def test_criacao_slug_duplicado_409():
    assert _create().status_code == 201
    r = _create(name="Outro nome")
    assert r.status_code == 409


def test_criacao_nivel_invalido_422():
    r = _create(level="mestre")
    assert r.status_code == 422


def test_criacao_media_sem_url_422():
    r = _create(media=[{"type": "video"}])
    assert r.status_code == 422


def test_criacao_campo_obrigatorio_ausente_422():
    payload = _payload()
    del payload["primary_muscle"]
    r = client.post("/admin/exercises", json=payload, headers=ADMIN_HEADERS)
    assert r.status_code == 422


def test_substituicao_duplicada_422():
    _create(slug="remada", name="Remada")
    r = _create(approved_substitutions=["remada", "remada"])
    assert r.status_code == 422


def test_substituicao_autorreferencia_422():
    r = _create(approved_substitutions=["supino-reto"])
    assert r.status_code == 422
    assert "autorreferencia" in r.json()["detail"].lower()


def test_substituicao_inexistente_422():
    r = _create(approved_substitutions=["nao-existe"])
    assert r.status_code == 422


def test_substituicao_valida_aceita():
    _create(slug="remada", name="Remada")
    r = _create(approved_substitutions=["remada"])
    assert r.status_code == 201
    assert r.json()["approved_substitutions"] == ["remada"]


# ---------------- listagem / filtros ----------------

def test_filtros_de_listagem():
    # Filtros vistos por autenticacao admin (enxerga ativos e inativos).
    _create(slug="supino", name="Supino", primary_muscle="Peito",
            equipment="Barra", level="iniciante")
    _create(slug="agacho", name="Agachamento", primary_muscle="Perna",
            equipment="Barra", level="avancado")
    _create(slug="rosca", name="Rosca", primary_muscle="Biceps",
            equipment="Halter", level="intermediario", is_active=False)

    assert len(client.get("/exercises", headers=ADMIN_HEADERS).json()) == 3
    assert len(client.get("/exercises?primary_muscle=Peito", headers=ADMIN_HEADERS).json()) == 1
    assert len(client.get("/exercises?equipment=Barra", headers=ADMIN_HEADERS).json()) == 2
    assert len(client.get("/exercises?level=avancado", headers=ADMIN_HEADERS).json()) == 1
    assert len(client.get("/exercises?is_active=false", headers=ADMIN_HEADERS).json()) == 1
    assert len(client.get("/exercises?is_active=true", headers=ADMIN_HEADERS).json()) == 2


def test_busca_textual_por_name_e_slug():
    _create(slug="supino-reto", name="Supino reto")
    _create(slug="agachamento-livre", name="Agachamento livre")
    # casa por name
    r1 = client.get("/exercises?q=agacha", headers=CLIENT_HEADERS)
    assert [e["slug"] for e in r1.json()] == ["agachamento-livre"]
    # casa por slug
    r2 = client.get("/exercises?q=supino", headers=CLIENT_HEADERS)
    assert [e["slug"] for e in r2.json()] == ["supino-reto"]


def test_resposta_publica_mostra_apenas_substituicoes_ativas():
    _create(slug="remada", name="Remada")
    _create(slug="puxada", name="Puxada")
    _create(slug="supino-reto", name="Supino", approved_substitutions=["remada", "puxada"])
    # desativa uma das substituicoes
    assert client.patch("/admin/exercises/puxada", json={"is_active": False},
                        headers=ADMIN_HEADERS).status_code == 200

    detail = client.get("/exercises/supino-reto", headers=CLIENT_HEADERS).json()
    assert detail["approved_substitutions"] == ["remada"]  # puxada (inativa) some


# ---------------- detalhe por slug ----------------

def test_detalhe_por_slug():
    _create()
    r = client.get("/exercises/supino-reto", headers=CLIENT_HEADERS)
    assert r.status_code == 200
    assert r.json()["name"] == "Supino reto"


def test_detalhe_inexistente_404():
    r = client.get("/exercises/nao-existe", headers=CLIENT_HEADERS)
    assert r.status_code == 404


# ---------------- edicao ----------------

def test_edicao_altera_campos():
    _create()
    r = client.patch("/admin/exercises/supino-reto",
                     json={"name": "Supino reto (barra)", "level": "intermediario"},
                     headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["name"] == "Supino reto (barra)"
    assert r.json()["level"] == "intermediario"


def test_edicao_exige_admin():
    _create()
    r = client.patch("/admin/exercises/supino-reto", json={"name": "X"}, headers=CLIENT_HEADERS)
    assert r.status_code == 403


def test_tentativa_de_mudar_slug_409():
    _create()
    r = client.patch("/admin/exercises/supino-reto", json={"slug": "outro-slug"}, headers=ADMIN_HEADERS)
    assert r.status_code == 409
    assert "imutavel" in r.json()["detail"].lower()


def test_mesmo_slug_no_patch_aceito():
    _create()
    r = client.patch("/admin/exercises/supino-reto",
                     json={"slug": "supino-reto", "name": "Novo"}, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["name"] == "Novo"


def test_desativacao_logica():
    _create()
    r = client.patch("/admin/exercises/supino-reto", json={"is_active": False}, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    # continua existindo (sem exclusao fisica): admin ainda consulta o registro.
    assert client.get("/exercises/supino-reto", headers=ADMIN_HEADERS).status_code == 200
    # cliente comum nao ve mais o inativo (nem no detalhe, nem na listagem).
    assert client.get("/exercises/supino-reto", headers=CLIENT_HEADERS).status_code == 404
    assert client.get("/exercises", headers=CLIENT_HEADERS).json() == []


def test_edicao_substituicao_invalida_422():
    _create()
    r = client.patch("/admin/exercises/supino-reto",
                     json={"approved_substitutions": ["fantasma"]}, headers=ADMIN_HEADERS)
    assert r.status_code == 422


def test_sem_exclusao_fisica():
    # DELETE nao e uma rota exposta nesta missao.
    _create()
    r = client.delete("/admin/exercises/supino-reto", headers=ADMIN_HEADERS)
    assert r.status_code == 405


# ---------------- regressao dos endpoints atuais ----------------

def test_rotas_existentes_intactas():
    paths = {getattr(r, "path", None) for r in app.routes}
    # rotas pre-existentes continuam registradas
    assert "/health" in paths
    assert "/auth/me" in paths
    # e as novas da LIB-003 foram adicionadas
    assert "/exercises" in paths
    assert "/exercises/{slug}" in paths
    assert "/admin/exercises" in paths
    assert "/admin/exercises/{slug}" in paths


def test_health_responde():
    r = client.get("/health")
    assert r.status_code in (200, 503)  # 503 se o engine real do main nao subir; rota existe


# ================================================================
# Regressoes dos blockers da auditoria Codex (PR #13)
# ================================================================

# ---- BLOCKER 1: gate administrativo oficial (sem bypass {0,2}) ----

def test_b1_cliente_comum_403():
    r = _create(as_admin=False)  # JWT de cliente id=99
    assert r.status_code == 403


def test_b1_client_id_2_nao_e_admin():
    # Prova a remocao do bypass {0,2}: um cliente com id=2 NAO e admin.
    headers = {"Authorization": f"Bearer {create_access_token(2)}"}
    r = client.post("/admin/exercises", json=_payload(), headers=headers)
    assert r.status_code == 403


def test_b1_api_administrativa_permitida():
    r = _create(as_admin=True)  # x-api-key oficial -> 0
    assert r.status_code == 201


# ---- BLOCKER 2: PATCH nunca aceita null em campo nao-anulavel (422) ----

def _patch_null(field, value=None):
    _create()
    return client.patch("/admin/exercises/supino-reto", json={field: value}, headers=ADMIN_HEADERS)


def test_b2_null_boolean_422():
    assert _patch_null("is_active").status_code == 422


def test_b2_null_string_422():
    assert _patch_null("name").status_code == 422
    # e o estado nao foi corrompido: registro segue integro
    body = client.get("/exercises/supino-reto", headers=ADMIN_HEADERS).json()
    assert body["name"] == "Supino reto"


def test_b2_null_enum_422():
    assert _patch_null("level").status_code == 422


def test_b2_null_lista_json_422():
    assert _patch_null("secondary_muscles").status_code == 422
    assert _patch_null("common_errors").status_code == 422
    assert _patch_null("cautions").status_code == 422


def test_b2_null_media_422():
    assert _patch_null("media").status_code == 422


def test_b2_null_substitutions_422():
    assert _patch_null("approved_substitutions").status_code == 422


def test_b2_instructions_aceita_null():
    # instructions e o unico campo anulavel do model: null e valido (nao 422).
    _create()
    r = client.patch("/admin/exercises/supino-reto", json={"instructions": None}, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["instructions"] is None


# ---- BLOCKER 3: slug precisa ser URL-safe / segmento unico (422) ----

def test_b3_slug_com_barra_422():
    assert _create(slug="supino/reto").status_code == 422


def test_b3_slug_com_espaco_422():
    assert _create(slug="supino reto").status_code == 422


def test_b3_slug_caracteres_invalidos_422():
    for ruim in ("supino#1", "supino?x", "supino%20", "acento-ç", "sup\tino"):
        assert _create(slug=ruim).status_code == 422, ruim


def test_b3_slug_valido_aceito():
    assert _create(slug="supino-reto_v2.1~a").status_code == 201


# ---- BLOCKER 4: unicidade garantida no commit (409), nao so no SELECT ----

def test_b4_slug_duplicado_no_commit_409():
    from unittest.mock import patch
    assert _create().status_code == 201
    # Simula a corrida: o SELECT previo NAO enxerga o registro (retorna None),
    # forcando o caminho a bater na unique constraint no commit -> 409 (nao 500).
    with patch("sqlalchemy.orm.query.Query.first", return_value=None):
        r = _create(name="Corrida")
    assert r.status_code == 409
    # rollback ocorreu: nao ficou lixo, o slug continua unico.
    assert len(client.get("/exercises?q=supino-reto", headers=ADMIN_HEADERS).json()) == 1


# ---- BLOCKER 5: cliente comum so ve ativos; inativo so por admin ----

def test_b5_cliente_ve_apenas_ativos_na_listagem():
    _create(slug="ativo", name="Ativo")
    _create(slug="inativo", name="Inativo", is_active=False)
    slugs = [e["slug"] for e in client.get("/exercises", headers=CLIENT_HEADERS).json()]
    assert slugs == ["ativo"]


def test_b5_cliente_nao_burla_via_filtro():
    _create(slug="inativo", name="Inativo", is_active=False)
    # mesmo pedindo is_active=false, o cliente comum nao recebe inativos.
    assert client.get("/exercises?is_active=false", headers=CLIENT_HEADERS).json() == []


def test_b5_admin_ve_inativos():
    _create(slug="inativo", name="Inativo", is_active=False)
    slugs = [e["slug"] for e in client.get("/exercises", headers=ADMIN_HEADERS).json()]
    assert "inativo" in slugs


def test_b5_cliente_detalhe_inativo_404():
    _create(slug="inativo", name="Inativo", is_active=False)
    assert client.get("/exercises/inativo", headers=CLIENT_HEADERS).status_code == 404


def test_b5_admin_detalhe_inativo_200():
    _create(slug="inativo", name="Inativo", is_active=False)
    assert client.get("/exercises/inativo", headers=ADMIN_HEADERS).status_code == 200


def test_b5_substituicoes_ativas_preservadas():
    # comportamento de substituicoes ativas continua valendo (nao regrediu).
    _create(slug="remada", name="Remada")
    _create(slug="puxada", name="Puxada")
    _create(slug="supino-reto", name="Supino", approved_substitutions=["remada", "puxada"])
    client.patch("/admin/exercises/puxada", json={"is_active": False}, headers=ADMIN_HEADERS)
    detail = client.get("/exercises/supino-reto", headers=CLIENT_HEADERS).json()
    assert detail["approved_substitutions"] == ["remada"]
