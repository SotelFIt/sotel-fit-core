"""Resolução de nomes de variáveis de ambiente de templates Twilio.

Camada PURA: só lê `os.environ`. Sem rede, sem DB, sem SDK — para ser testável
isoladamente (sem puxar fastapi/dotenv/twilio).

Contexto: durante a transição de nomenclatura, o SID do template de retenção pode
estar sob o nome oficial (inglês) OU o antigo (português). Esta função aceita os
dois, com precedência do nome oficial. Nunca expõe o valor — apenas o resolve.
"""
import os
from typing import Optional


def retention_template_sid() -> Optional[str]:
    """SID do template de retenção.

    Aceita `TWILIO_TEMPLATE_RETENTION` (nome oficial) e, como fallback de
    transição, `TWILIO_TEMPLATE_RETENCAO`. Retorna None se nenhum estiver
    configurado — nesse caso o chamador NÃO deve acionar o Twilio.
    """
    return os.getenv("TWILIO_TEMPLATE_RETENTION") or os.getenv("TWILIO_TEMPLATE_RETENCAO")
