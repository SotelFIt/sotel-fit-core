"""
LIB-007A - testes do importador seguro (tools/import_exercise_catalog.py).

Sem rede real, sem producao, sem token real. Usa httpx.MockTransport como
servidor fake da API oficial. Cobre validacao do catalogo, idempotencia,
recuperacao de ambiguidade, --limit, conflito isolado por exercicio, seguranca da chave
e a contagem exata do catalogo oficial (25).
"""
import json
import os
import sys

import httpx
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.abspath(os.path.join(_HERE, ".."))
_ROOT = os.path.abspath(os.path.join(_APP, ".."))
_TOOLS = os.path.join(_ROOT, "tools")
sys.path.insert(0, _APP)
sys.path.insert(0, _TOOLS)

import import_exercise_catalog as imp  # noqa: E402
from schemas.exercise import ExerciseCreate  # noqa: E402

CATALOG_PATH = os.path.join(_APP, "data", "exercise_catalog_sprint1.json")


# --------------------------- servidor fake --------------------------- #

class FakeApi:
    def __init__(self):
        self.store = {}          # slug -> full response
        self.hidden = set()      # slugs ocultos da listagem (simula item criado apos o list inicial)
        self.post_behaviors = {} # slug -> lista de comportamentos ("timeout","500")
        self.post_calls = []     # ordem dos POSTs
        self._id = 0

    def insert(self, entry):
        payload = ExerciseCreate(**entry).model_dump()
        self._id += 1
        resp = {**payload, "id": self._id,
                "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}
        self.store[payload["slug"]] = resp
        return resp

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/exercises":
            visible = [v for s, v in self.store.items() if s not in self.hidden]
            return httpx.Response(200, json=visible)
        if request.method == "GET" and path.startswith("/exercises/"):
            slug = path[len("/exercises/"):]
            if slug in self.store:
                return httpx.Response(200, json=self.store[slug])
            return httpx.Response(404, json={"detail": "nao encontrado"})
        if request.method == "POST" and path == "/admin/exercises":
            payload = json.loads(request.content)
            slug = payload["slug"]
            self.post_calls.append(slug)
            beh = self.post_behaviors.get(slug)
            if beh:
                step = beh.pop(0)
                # str legado ("timeout"/"500") ou dict {"code":..,"store":"equal"|"divergent"}
                if isinstance(step, str):
                    step = {"code": "timeout" if step == "timeout" else int(step)}
                store = step.get("store")
                if store == "equal":
                    self.insert(payload)               # servidor gravou versao equivalente
                elif store == "divergent":
                    d = dict(payload)
                    d["aliases"] = list(payload.get("aliases", [])) + ["ZZZ Divergente"]
                    self.insert(d)                     # servidor gravou versao divergente
                code = step["code"]
                if code == "timeout":
                    raise httpx.TimeoutException("simulado", request=request)
                if code == 201:
                    return httpx.Response(201, json=self.store[slug])
                return httpx.Response(code, json={"detail": "beh"})
            if slug in self.store:
                return httpx.Response(409, json={"detail": f"slug ja existe: {slug}"})
            return httpx.Response(201, json=self.insert(payload))
        return httpx.Response(404)


def _client(fake):
    return httpx.Client(transport=httpx.MockTransport(fake.handler), base_url="http://test")


def _entry(slug, name, aliases=None, muscle="peitoral", equip="maquina", level="iniciante"):
    return {"slug": slug, "name": name, "aliases": aliases or [], "primary_muscle": muscle,
            "equipment": equip, "level": level, "is_active": True}


def _catalog(entries):
    return {"exercises": entries}


def _run(fake, entries, **kw):
    kw.setdefault("expected_count", None)
    return imp.run_import(_client(fake), _catalog(entries), **kw)


# --------------------------- Gate 4: validacao --------------------------- #

def test_01_catalogo_oficial_valido():
    catalog = imp.load_catalog(CATALOG_PATH)
    payloads = imp.validate_catalog(catalog)  # expected_count=25 default
    assert len(payloads) == 25


def test_25_catalogo_oficial_tem_exatamente_25():
    catalog = imp.load_catalog(CATALOG_PATH)
    assert len(catalog["exercises"]) == 25
    with pytest.raises(imp.CatalogError):
        imp.validate_catalog({"exercises": catalog["exercises"][:24]})  # 24 != 25


def test_02_slug_duplicado():
    entries = [_entry("a", "Alfa"), _entry("a", "Beta")]
    with pytest.raises(imp.CatalogError, match="slug duplicado"):
        imp.validate_catalog(_catalog(entries), expected_count=None)


def test_03_nome_canonico_normalizado_duplicado():
    entries = [_entry("a", "Supino Reto"), _entry("b", "supino reto")]
    with pytest.raises(imp.CatalogError, match="canonico normalizado duplicado"):
        imp.validate_catalog(_catalog(entries), expected_count=None)


def test_04_alias_duplicado_normalizado_no_mesmo():
    entries = [_entry("a", "Alfa", aliases=["Push Up", "Push-Up"])]  # ambos -> "push up"
    with pytest.raises(imp.CatalogError, match="alias duplicado"):
        imp.validate_catalog(_catalog(entries), expected_count=None)


def test_05_alias_colide_com_canonico_de_outro():
    entries = [_entry("a", "Leg Press"), _entry("b", "Outro", aliases=["leg press"])]
    with pytest.raises(imp.CatalogError, match="nome canonico de slug"):
        imp.validate_catalog(_catalog(entries), expected_count=None)


def test_06_alias_colide_com_alias_de_outro():
    entries = [_entry("a", "Alfa", aliases=["Sinonimo X"]),
               _entry("b", "Beta", aliases=["sinonimo x"])]
    with pytest.raises(imp.CatalogError, match="colide com alias"):
        imp.validate_catalog(_catalog(entries), expected_count=None)


def test_07_alias_redundante_com_proprio_canonico():
    entries = [_entry("a", "Rosca Direta", aliases=["rosca direta"])]
    with pytest.raises(imp.CatalogError, match="redundante"):
        imp.validate_catalog(_catalog(entries), expected_count=None)


def test_08_campo_invalido_rejeitado_por_ExerciseCreate():
    bad = _entry("a", "Alfa")
    bad["level"] = "expert"  # fora do enum
    with pytest.raises(imp.CatalogError):
        imp.validate_catalog(_catalog([bad]), expected_count=None)
    # campo inesperado
    extra = _entry("b", "Beta"); extra["foo"] = 1
    with pytest.raises(imp.CatalogError, match="campos inesperados"):
        imp.validate_catalog(_catalog([extra]), expected_count=None)
    # alias vazio
    empty = _entry("c", "Gama", aliases=["  "])
    with pytest.raises(imp.CatalogError, match="alias vazio"):
        imp.validate_catalog(_catalog([empty]), expected_count=None)


# --------------------------- Gate 6/8: fluxo --------------------------- #

def test_09_dry_run_nunca_faz_post():
    fake = FakeApi()
    rep = _run(fake, [_entry("a", "Alfa"), _entry("b", "Beta")], apply=False)
    assert fake.post_calls == []
    assert rep["mode"] == "dry-run"


def test_10_ausente_vira_would_create():
    fake = FakeApi()
    rep = _run(fake, [_entry("a", "Alfa")], apply=False)
    assert rep["results"][0]["status"] == "would_create"


def test_11_existente_equivalente_vira_skipped_equal():
    fake = FakeApi()
    e = _entry("a", "Alfa", aliases=["A1"])
    fake.insert(e)
    rep = _run(fake, [e], apply=True)
    assert rep["results"][0]["status"] == "skipped_equal"
    assert fake.post_calls == []  # nao faz POST nem PATCH


def test_12_existente_divergente_vira_conflict():
    fake = FakeApi()
    fake.insert(_entry("a", "Alfa", aliases=["Antigo"]))
    rep = _run(fake, [_entry("a", "Alfa", aliases=["Novo"])], apply=True)
    r = rep["results"][0]
    assert r["status"] == "conflict"
    assert "aliases" in r["diffs"]
    assert fake.post_calls == []


def test_13_conflito_isolado_nao_bloqueia_posteriores():
    # LIB-007A.1: conflito no item 'a' NAO bloqueia; 'b' (ausente) e criado.
    fake = FakeApi()
    fake.insert(_entry("a", "Alfa", aliases=["Antigo"]))
    entries = [_entry("a", "Alfa", aliases=["Novo"]), _entry("b", "Beta")]
    rep = _run(fake, entries, apply=True)
    by = {r["slug"]: r["status"] for r in rep["results"]}
    assert by["a"] == "conflict"          # divergente, sem POST
    assert by["b"] == "created"           # posterior continua sendo criado
    assert fake.post_calls == ["b"]       # 'a' nao recebe POST; so 'b'
    assert "skipped_blocked" not in {r["status"] for r in rep["results"]}


def test_13b_multiplos_conflitos_registrados_individualmente():
    fake = FakeApi()
    fake.insert(_entry("a", "Alfa", aliases=["Antigo"]))
    fake.insert(_entry("c", "Gama", aliases=["Antigo C"]))
    entries = [_entry("a", "Alfa", aliases=["Novo"]),
               _entry("b", "Beta"),
               _entry("c", "Gama", aliases=["Novo C"])]
    rep = _run(fake, entries, apply=True)
    by = {r["slug"]: r["status"] for r in rep["results"]}
    assert by == {"a": "conflict", "b": "created", "c": "conflict"}
    assert rep["counts"]["conflict"] == 2
    assert fake.post_calls == ["b"]  # so o ausente
    # cada conflito registra seus campos divergentes
    for r in rep["results"]:
        if r["status"] == "conflict":
            assert r["diffs"] == ["aliases"]


def test_13c_dry_run_conflito_isolado_demais_would_create():
    fake = FakeApi()
    fake.insert(_entry("a", "Alfa", aliases=["Antigo"]))
    rep = _run(fake, [_entry("a", "Alfa", aliases=["Novo"]), _entry("b", "Beta")], apply=False)
    by = {r["slug"]: r["status"] for r in rep["results"]}
    assert by == {"a": "conflict", "b": "would_create"}
    assert fake.post_calls == []


def test_14_apply_cria_ausente():
    fake = FakeApi()
    rep = _run(fake, [_entry("a", "Alfa")], apply=True)
    assert rep["results"][0]["status"] == "created"
    assert fake.post_calls == ["a"]
    assert "a" in fake.store


def test_15_confirmacao_por_get_apos_criacao():
    fake = FakeApi()
    rep = _run(fake, [_entry("a", "Alfa")], apply=True)
    # created so ocorre se o GET pos-POST encontrou o slug equivalente
    assert rep["results"][0]["status"] == "created"
    assert fake.store["a"]["name"] == "Alfa"


def test_16_timeout_com_get_equivalente_vira_ambiguous_recovered():
    fake = FakeApi()
    e = _entry("a", "Alfa")
    fake.insert(e)          # como se tivesse sido criado
    fake.hidden.add("a")    # oculto da listagem inicial -> importer ve "ausente"
    fake.post_behaviors["a"] = ["timeout"]
    rep = _run(fake, [e], apply=True)
    assert rep["results"][0]["status"] == "ambiguous_recovered"
    assert fake.post_calls == ["a"]  # nao repetiu POST


def test_17_timeout_com_get_inexistente_permite_uma_retentativa():
    fake = FakeApi()
    fake.post_behaviors["a"] = ["timeout", "timeout"]  # 1a e 2a falham
    rep = _run(fake, [_entry("a", "Alfa")], apply=True)
    assert rep["results"][0]["status"] == "failed"
    assert fake.post_calls == ["a", "a"]  # exatamente 2 (sem loop)


def test_17b_timeout_depois_sucesso_cria():
    fake = FakeApi()
    fake.post_behaviors["a"] = ["timeout"]  # 1a falha, 2a cria
    rep = _run(fake, [_entry("a", "Alfa")], apply=True)
    assert rep["results"][0]["status"] == "created"
    assert fake.post_calls == ["a", "a"]


def test_18_http_409_equivalente_nao_duplica():
    fake = FakeApi()
    e = _entry("a", "Alfa", aliases=["A1"])
    fake.insert(e)
    fake.hidden.add("a")  # ausente na listagem inicial, mas POST retorna 409
    rep = _run(fake, [e], apply=True)
    assert rep["results"][0]["status"] == "skipped_equal"
    assert len(fake.store) == 1  # sem duplicata


def test_19_http_409_divergente_vira_conflict():
    fake = FakeApi()
    fake.insert(_entry("a", "Alfa", aliases=["Antigo"]))
    fake.hidden.add("a")
    rep = _run(fake, [_entry("a", "Alfa", aliases=["Novo"])], apply=True)
    assert rep["results"][0]["status"] == "conflict"


# --------------- LIB-007A.2: recuperacao de 409/5xx apos retentativa de 5xx --------------- #

def test_a2_1_retry_apos_500_409_equivalente_vira_ambiguous_recovered():
    fake = FakeApi()
    fake.post_behaviors["a"] = [{"code": 500}, {"code": 409, "store": "equal"}]
    rep = _run(fake, [_entry("a", "Alfa")], apply=True)
    assert rep["results"][0]["status"] == "ambiguous_recovered"
    assert fake.post_calls == ["a", "a"]  # exatamente 2 POSTs


def test_a2_2_retry_apos_500_409_divergente_vira_conflict():
    fake = FakeApi()
    fake.post_behaviors["a"] = [{"code": 500}, {"code": 409, "store": "divergent"}]
    rep = _run(fake, [_entry("a", "Alfa")], apply=True)
    r = rep["results"][0]
    assert r["status"] == "conflict"
    assert "aliases" in r["diffs"]
    assert fake.post_calls == ["a", "a"]


def test_a2_3_retry_apos_500_409_ausente_vira_failed():
    fake = FakeApi()
    fake.post_behaviors["a"] = [{"code": 500}, {"code": 409}]  # 409 sem gravar -> GET ausente
    rep = _run(fake, [_entry("a", "Alfa")], apply=True)
    assert rep["results"][0]["status"] == "failed"
    assert fake.post_calls == ["a", "a"]


def test_a2_4_retry_apos_500_novo_500_equivalente_ambiguous_sem_terceiro_post():
    fake = FakeApi()
    fake.post_behaviors["a"] = [{"code": 500}, {"code": 500, "store": "equal"}]
    rep = _run(fake, [_entry("a", "Alfa")], apply=True)
    assert rep["results"][0]["status"] == "ambiguous_recovered"
    assert fake.post_calls == ["a", "a"]  # nenhum 3o POST


def test_20_limit_cria_no_maximo_n():
    fake = FakeApi()
    entries = [_entry(f"s{i}", f"Nome {i}") for i in range(8)]
    rep = _run(fake, entries, apply=True, limit=5)
    assert rep["created_total"] == 5
    assert len(fake.post_calls) == 5
    statuses = [r["status"] for r in rep["results"]]
    assert statuses.count("created") == 5
    assert statuses.count("skipped_limit") == 3


def test_20b_limit_conta_apenas_criacoes_nao_conflitos():
    # 2 conflitos + 8 ausentes, limit=5 -> 5 criacoes; conflitos nao consomem limite.
    fake = FakeApi()
    fake.insert(_entry("cA", "Conf A", aliases=["Antigo A"]))
    fake.insert(_entry("cB", "Conf B", aliases=["Antigo B"]))
    entries = ([_entry("cA", "Conf A", aliases=["Novo A"])] +
               [_entry(f"s{i}", f"Nome {i}") for i in range(4)] +
               [_entry("cB", "Conf B", aliases=["Novo B"])] +
               [_entry(f"t{i}", f"T {i}") for i in range(4)])
    rep = _run(fake, entries, apply=True, limit=5)
    c = rep["counts"]
    assert c["conflict"] == 2
    assert rep["created_total"] == 5
    assert c["created"] == 5
    assert c["skipped_limit"] == 3  # 8 ausentes - 5 criados


def test_prod_cenario_flexao_conflict_demais_criados():
    """Cenario equivalente a producao: flexao-de-bracos existente e divergente
    por aliases; os outros 24 ausentes continuam sendo criados. Usa o catalogo
    OFICIAL (25) para provar 1 conflict + 24 created, sem skipped_blocked."""
    catalog = imp.load_catalog(CATALOG_PATH)
    fake = FakeApi()
    # producao: flexao com o alias redundante extra 'Push-Up'
    fake.insert({"slug": "flexao-de-bracos", "name": "Flexão de Braços",
                 "aliases": ["Flexão", "Push Up", "Push-Up", "Flexão no Solo"],
                 "primary_muscle": "peitoral", "equipment": "peso corporal",
                 "level": "iniciante", "is_active": True})
    fake.hidden.discard("flexao-de-bracos")  # visivel na listagem inicial
    rep = imp.run_import(_client(fake), catalog, apply=True, base_url="http://mock")
    c = rep["counts"]
    assert c["conflict"] == 1
    assert rep["created_total"] == 24
    assert c["created"] == 24
    assert "skipped_blocked" not in c
    flex = [r for r in rep["results"] if r["slug"] == "flexao-de-bracos"][0]
    assert flex["status"] == "conflict" and flex["diffs"] == ["aliases"]


def test_21_segunda_execucao_idempotente():
    fake = FakeApi()
    entries = [_entry("a", "Alfa"), _entry("b", "Beta")]
    _run(fake, entries, apply=True)
    fake.post_calls.clear()
    rep2 = _run(fake, entries, apply=True)
    assert all(r["status"] == "skipped_equal" for r in rep2["results"])
    assert fake.post_calls == []  # nada recriado


def test_24_processamento_sequencial_na_ordem_do_json():
    fake = FakeApi()
    entries = [_entry("x1", "X1"), _entry("x2", "X2"), _entry("x3", "X3")]
    _run(fake, entries, apply=True)
    assert fake.post_calls == ["x1", "x2", "x3"]


# --------------------------- Gate 3/9: seguranca da chave --------------------------- #

def test_22_apply_sem_env_bloqueia(monkeypatch):
    monkeypatch.delenv(imp.API_KEY_ENV, raising=False)
    rc = imp.main(["--catalog", CATALOG_PATH, "--base-url", "http://x", "--apply"])
    assert rc == 2  # parou antes de qualquer request


def test_23_segredo_nunca_no_relatorio():
    SECRET = "chave-super-secreta-1234"
    fake = FakeApi()
    client = httpx.Client(transport=httpx.MockTransport(fake.handler),
                          base_url="http://test", headers={"x-api-key": SECRET})
    rep = imp.run_import(client, _catalog([_entry("a", "Alfa")]), apply=True,
                         expected_count=None, base_url="http://test")
    blob = json.dumps(rep, ensure_ascii=False)
    assert SECRET not in blob
    assert "x-api-key" not in blob
    assert "authorization" not in blob.lower()
