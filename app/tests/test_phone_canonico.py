"""
REL-V1-004 - identidade canonica de telefone (E.164).

O normalizador ja era unico e ja acertava numero brasileiro valido. O defeito
estava do outro lado: entrada que NAO e telefone virava telefone plausivel
("abc" -> "+55"), a repeticao colava outro "55" a cada chamada, e um E.164
estrangeiro era reinterpretado como brasileiro.

Estes testes travam as duas metades:
  - a saida canonica dos VALIDOS nao pode mudar (mudaria a identidade de quem
    ja existe em producao);
  - entrada invalida devolve None e nunca e persistida.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.phone import normalize_phone, normalize_phone_for_whatsapp

CANONICO = "+5517991089991"


# ---------------- A/B/C/D: formatos equivalentes ----------------

@pytest.mark.parametrize("entrada", [
    "+5517991089991",          # ja canonico
    "+55 17 99108-9991",       # A - com DDI e formatado
    "17991089991",             # B - BR sem DDI
    "(17) 99108-9991",         # C - mascara brasileira
    "whatsapp:+5517991089991",  # D - prefixo do Twilio
    "  17 99108 9991  ",       # espacos
    "5517991089991",           # DDI sem o '+'
])
def test_formatos_equivalentes_produzem_a_mesma_identidade(entrada):
    assert normalize_phone(entrada) == CANONICO


def test_fixo_de_oito_digitos_continua_valido():
    assert normalize_phone("1733221234") == "+551733221234"


def test_ddd_55_nao_e_confundido_com_ddi():
    """DDD 55 (RS) sem DDI: o 55 da frente e area, nao pais."""
    assert normalize_phone("55999998888") == "+5555999998888"
    assert normalize_phone("5555999998888") == "+5555999998888"


# ---------------- E: idempotencia ----------------

@pytest.mark.parametrize("entrada", [
    "+55 17 99108-9991", "17991089991", "(17) 99108-9991",
    "whatsapp:+5517991089991", "1733221234", "55999998888",
])
def test_normalizar_duas_vezes_nao_muda_nada(entrada):
    uma = normalize_phone(entrada)
    assert normalize_phone(uma) == uma


# ---------------- F/G/H/I: entrada invalida ----------------

@pytest.mark.parametrize("entrada", [
    "abc",        # F - nao ha numero
    "123",        # G - curto demais
    "+55",        # H - so o DDI
    "55",
    "",
    "   ",
    None,
    "whatsapp:",
    "0199999999",  # DDD 01 nao existe
    "12345678901234567890",  # longo demais para E.164
])
def test_entrada_invalida_devolve_none(entrada):
    assert normalize_phone(entrada) is None


def test_repetir_a_normalizacao_de_invalido_nunca_produz_telefone():
    """I - antes, cada chamada colava outro '55': +55 -> +5555 -> +555555."""
    v = "abc"
    for _ in range(5):
        v = normalize_phone(v)
        assert v is None


# ---------------- J: internacional ----------------

def test_e164_estrangeiro_nao_vira_brasileiro():
    assert normalize_phone("+1 555 123 4567") == "+15551234567"
    assert normalize_phone("+351912345678") == "+351912345678"


def test_estrangeiro_e_idempotente():
    uma = normalize_phone("+1 555 123 4567")
    assert normalize_phone(uma) == uma


# ---------------- whatsapp ----------------

def test_formato_whatsapp_segue_a_mesma_identidade():
    assert normalize_phone_for_whatsapp("(17) 99108-9991") == "whatsapp:" + CANONICO


def test_whatsapp_de_invalido_e_none_e_nao_string_quebrada():
    """Antes viria 'whatsapp:+55', que o Twilio aceitaria como destino."""
    assert normalize_phone_for_whatsapp("abc") is None
    assert normalize_phone_for_whatsapp(None) is None


# ---------------- K/L/M: write path e regressao ----------------

def test_write_path_recusa_criar_cliente_sem_identidade():
    """K - get_or_create_client_from_phone nao pode inventar um cliente."""
    from services.client_service import get_or_create_client_from_phone
    with pytest.raises(ValueError):
        get_or_create_client_from_phone(None, "abc")
    with pytest.raises(ValueError):
        get_or_create_client_from_phone(None, "+55")


def test_onboarding_de_lead_recusa_telefone_invalido():
    """K - o router publico recusa antes de gravar (convencao 400 do projeto)."""
    import inspect
    from routers import lead_onboarding
    src = inspect.getsource(lead_onboarding.create_lead_onboarding)
    assert "if not phone_normalized" in src
    assert "400" in src


def test_saida_canonica_dos_validos_nao_mudou(  ):
    """M/L - contrato preservado: estes valores JA estao gravados em producao.
    Se algum mudasse, clientes existentes deixariam de ser encontrados."""
    esperado = {
        "+55 17 99108-9991": "+5517991089991",
        "17991089991": "+5517991089991",
        "(17) 99108-9991": "+5517991089991",
        "whatsapp:+5517991089991": "+5517991089991",
        "1733221234": "+551733221234",
        "55999998888": "+5555999998888",
    }
    for entrada, saida in esperado.items():
        assert normalize_phone(entrada) == saida, entrada
