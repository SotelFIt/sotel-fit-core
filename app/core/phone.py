"""
phone - identidade canonica de telefone (E.164).

Normalizador UNICO do projeto: 8 caminhos de escrita/consulta dependem dele.
Nao criar um segundo em nenhuma camada.

REL-V1-004: a funcao continua produzindo EXATAMENTE o mesmo canonico para toda
entrada brasileira valida - mudar isso mudaria a identidade de clientes que ja
existem. O que muda e o tratamento do que nao e telefone:

    antes                             agora
    "abc"  -> "+55"                   None
    "123"  -> "+55123"                None
    "+55"  -> "+5555"                 None
    normalizar de novo colava "55"    None continua None
    "+1 555 123 4567" -> "+55155..."  "+15551234567" (preservado)

Parsing pode remover espaco, parenteses, hifen e o prefixo "whatsapp:".
Parsing NAO pode transformar lixo em identidade: nao inventa DDD, nao completa
digito, nao adota pais por heuristica. Entrada que nao e telefone retorna None,
e cabe a quem chama recusar a escrita.
"""
import re
from typing import Optional

# BR: DDI 55 + DDD (2) + assinante (8 fixo | 9 movel).
DDD_MIN, DDD_MAX = 11, 99
_LOCAL_BR = (8, 9)
# E.164 admite de 8 a 15 digitos no total, incluindo o codigo do pais.
E164_MIN, E164_MAX = 8, 15


def _ddd_valido(ddd: str) -> bool:
    return ddd.isdigit() and DDD_MIN <= int(ddd) <= DDD_MAX


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Telefone canonico em E.164, ou None quando a entrada nao e um telefone.

    None e um resultado legitimo e significa "isto nao identifica ninguem" -
    nunca deve ser persistido como se fosse um numero.
    """
    if not phone:
        return None

    p = str(phone).strip()
    if p.lower().startswith("whatsapp:"):
        p = p[9:].strip()

    tinha_mais = p.startswith("+")
    digits = re.sub(r"\D", "", p)
    if not digits:
        return None

    # E.164 estrangeiro: preservado como veio. Nao vira brasileiro em hipotese
    # alguma - reinterpretar o pais seria inventar outra identidade.
    if tinha_mais and not digits.startswith("55"):
        return "+" + digits if E164_MIN <= len(digits) <= E164_MAX else None

    # BR ja com o DDI: 55 + DDD + 8/9 digitos.
    if digits.startswith("55") and len(digits) in (12, 13):
        ddd, local = digits[2:4], digits[4:]
        if _ddd_valido(ddd) and len(local) in _LOCAL_BR:
            return "+" + digits
        return None

    # BR sem DDI: DDD + 8/9 digitos.
    if len(digits) in (10, 11):
        ddd = digits[:2]
        if _ddd_valido(ddd):
            return "+55" + digits
        return None

    return None


def normalize_phone_for_whatsapp(phone: Optional[str]) -> Optional[str]:
    """Mesma identidade, no formato que o Twilio espera. None quando invalida."""
    canonico = normalize_phone(phone)
    return "whatsapp:" + canonico if canonico else None
