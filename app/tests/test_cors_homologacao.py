"""
CORS — origem de homologação com MENOR ACESSO POSSÍVEL.

Contexto: previews do cliente não eram aceitos pela API. O preflight voltava
400, o navegador bloqueava a chamada e a tela de login exibia
"E-mail não encontrado" para uma conta que existia e estava ativa — falha de
transporte virando afirmação sobre a conta.

A liberação é de UMA origem exata, não de um padrão. Estes testes existem para
impedir que alguém "simplifique" isso depois para um curinga.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault("JWT_SECRET_KEY", "ec/hBUFhntuNSkRbbVvo6CnWDOkXV2b8TMLI5vMcFd8=")
os.environ.setdefault("LANDBOT_SECRET_TOKEN", "token-admin-teste")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from main import app  # noqa: E402

PREVIEW = "https://sotel-client-c6fjnd8kk-sotelfits-projects.vercel.app"


def _cors():
    for m in app.user_middleware:
        if m.cls is CORSMiddleware:
            return m.kwargs
    raise AssertionError("CORSMiddleware nao esta configurado")


def test_a_origem_exata_do_preview_esta_liberada():
    assert PREVIEW in _cors()["allow_origins"]


def test_a_liberacao_e_de_UMA_origem_exata_nao_de_um_padrao():
    """Menor acesso possível: nada de curinga para previews do cliente."""
    regex = _cors().get("allow_origin_regex") or ""
    assert "sotel-client" not in regex, (
        "um padrao para previews do cliente liberaria todo deployment, de "
        "qualquer branch, presente e futuro — foi exatamente o que o "
        "Proprietario recusou"
    )
    for origem in _cors()["allow_origins"]:
        assert "*" not in origem, f"curinga na allowlist: {origem}"


def test_a_regra_do_admin_continua_intacta():
    assert _cors()["allow_origin_regex"] == r"https://sotel-admin-git-.*-sotelfits-projects\.vercel\.app"


def test_outro_preview_do_cliente_NAO_esta_liberado():
    """Vizinho parecido continua fora — é o que prova que não virou padrão."""
    permitidas = set(_cors()["allow_origins"])
    import re

    regex = _cors()["allow_origin_regex"]
    for vizinha in [
        "https://sotel-client-73jru9m7m-sotelfits-projects.vercel.app",
        "https://sotel-client-gx9xmnn69-sotelfits-projects.vercel.app",
        "https://sotel-client-c6fjnd8kk-sotelfits-projects.vercel.app.evil.com",
        # a origem da homologacao ANTERIOR: foi SUBSTITUIDA, nao acumulada
        "https://sotel-client-8k6idllvi-sotelfits-projects.vercel.app",
        "https://sotel-client-c6fjnd8kk-sotelfits-projects.vercel.app.br",
        "http://sotel-client-c6fjnd8kk-sotelfits-projects.vercel.app",
    ]:
        assert vizinha not in permitidas, f"origem nao autorizada na allowlist: {vizinha}"
        assert not re.fullmatch(regex, vizinha), f"regex do admin aceitou {vizinha}"


def test_as_origens_de_producao_continuam_valendo():
    permitidas = set(_cors()["allow_origins"])
    assert "https://sotel-client.vercel.app" in permitidas
    assert "https://sotel-admin.vercel.app" in permitidas


def test_credenciais_e_metodos_nao_foram_afrouxados():
    """A missao autoriza CORS — nada alem disso."""
    c = _cors()
    assert c["allow_credentials"] is True
    assert c["allow_methods"] == ["*"]
    assert c["allow_headers"] == ["*"]
