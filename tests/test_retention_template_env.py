"""Testes do resolvedor de env do template de retenção (fix/retention-template-env).

Camada PURA: só leem variáveis de ambiente. NENHUMA chamada externa (rede/DB/SDK).
O import puxa apenas `core.twilio_env` (stdlib), não o app (fastapi/dotenv/twilio).

Rodar: python -m unittest discover -s tests -p "test_*.py"
"""
import os
import sys
import socket
import unittest

# Torna 'core.twilio_env' importável sem puxar as deps pesadas do app.
APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APP_DIR)

from core.twilio_env import retention_template_sid  # noqa: E402

VARS = ("TWILIO_TEMPLATE_RETENTION", "TWILIO_TEMPLATE_RETENCAO")


class RetentionTemplateEnvTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in VARS}
        for k in VARS:
            os.environ.pop(k, None)

    def tearDown(self):
        for k in VARS:
            v = self._saved.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_nome_ingles_funciona(self):
        os.environ["TWILIO_TEMPLATE_RETENTION"] = "HX_en"
        self.assertEqual(retention_template_sid(), "HX_en")

    def test_fallback_portugues_funciona(self):
        os.environ["TWILIO_TEMPLATE_RETENCAO"] = "HX_pt"
        self.assertEqual(retention_template_sid(), "HX_pt")

    def test_ingles_tem_precedencia_sobre_o_fallback(self):
        os.environ["TWILIO_TEMPLATE_RETENTION"] = "HX_en"
        os.environ["TWILIO_TEMPLATE_RETENCAO"] = "HX_pt"
        self.assertEqual(retention_template_sid(), "HX_en")

    def test_ausencia_dos_dois_retorna_none(self):
        # None => o endpoint NÃO chama o Twilio (guard `if not content_sid`).
        self.assertIsNone(retention_template_sid())

    def test_nenhuma_chamada_externa_de_rede(self):
        # Bloqueia sockets: se o resolver tentasse rede, o teste falharia.
        orig = socket.socket
        socket.socket = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("rede proibida neste teste")
        )
        try:
            os.environ["TWILIO_TEMPLATE_RETENTION"] = "HX_en"
            self.assertEqual(retention_template_sid(), "HX_en")
            os.environ.pop("TWILIO_TEMPLATE_RETENTION", None)
            self.assertIsNone(retention_template_sid())
        finally:
            socket.socket = orig


if __name__ == "__main__":
    unittest.main()
