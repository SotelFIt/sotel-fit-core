import json
import logging
import os

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.metodo_sotel import decidir

logger = logging.getLogger(__name__)


def _buscar_onboarding(db: Session, client_id: int):
    """client_id -> telefone (clients) -> lead_onboardings."""
    client_row = db.execute(
        text("SELECT phone FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()

    if not client_row or not client_row[0]:
        raise HTTPException(
            status_code=404,
            detail="Cliente nao encontrado ou sem telefone cadastrado."
        )

    phone = client_row[0]
    phone_clean = phone.replace("whatsapp:", "")

    o = db.execute(
        text("""
            SELECT objetivo, meta_principal, peso, altura, idade,
                   alimentacao_atual, maior_dificuldade, observacoes
            FROM lead_onboardings
            WHERE phone = :p OR phone = :pc OR phone = :pw
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"p": phone, "pc": phone_clean, "pw": f"whatsapp:{phone_clean}"}
    ).fetchone()

    if not o:
        raise HTTPException(
            status_code=404,
            detail="Cliente ainda nao completou o onboarding. Nao ha dados para gerar a dieta."
        )

    return {
        "objetivo": o[0],
        "meta_principal": o[1],
        "peso": o[2],
        "altura": o[3],
        "idade": o[4],
        "alimentacao_atual": o[5],
        "maior_dificuldade": o[6],
        "observacoes": o[7],
    }


def _extrair_preferencias(observacoes) -> dict:
    """Parse seguro do JSON observacoes. Retorna {} se falhar."""
    if not observacoes:
        return {}
    try:
        data = json.loads(observacoes)
        if isinstance(data, dict):
            return data
    except Exception as e:
        logger.warning(f"observacoes nao e JSON valido: {e}")
    return {}


def _montar_prompt(dados: dict, prefs: dict, diretriz_sotel: str = "") -> str:
    return f"""Voce e um assistente de prescricao alimentar para consultoria fitness, gerando apenas um rascunho para revisao profissional.

Dados do cliente:
- Objetivo principal: {dados.get('objetivo') or 'nao informado'}
- Meta principal: {dados.get('meta_principal') or 'nao informado'}
- Peso: {dados.get('peso') or 'nao informado'} kg | Altura: {dados.get('altura') or 'nao informado'} cm | Idade: {dados.get('idade') or 'nao informado'}
- Alimentacao atual: {dados.get('alimentacao_atual') or 'nao informado'}
- Maior dificuldade: {dados.get('maior_dificuldade') or 'nao informado'}
- Alimentos que gosta: {prefs.get('alimentos_gosta') or 'nao informado'}
- Alimentos que NAO gosta: {prefs.get('alimentos_nao_gosta') or 'nao informado'}

RESTRICOES OBRIGATORIAS (NUNCA INCLUIR):
- Alergias: {prefs.get('alergias') or 'nenhuma informada'}
- Restricoes: {prefs.get('restricoes') or 'nenhuma informada'}

DIRETRIZ ESTRATEGICA DO METODO SOTEL (seguir obrigatoriamente):
{diretriz_sotel}

Gere um rascunho de plano alimentar diario estruturado, RESPEITANDO a diretriz estrategica acima.

FORMATO OBRIGATORIO:
- Organizar por refeicoes (Cafe da manha, Lanche, Almoco, Lanche da tarde, Jantar, Ceia)
- Cada refeicao com horario sugerido, alimentos e quantidades aproximadas
- Incluir recomendacao de agua diaria
- Maximo 600 palavras

REGRAS CRITICAS:
- JAMAIS incluir alimentos listados em alergias ou restricoes (risco a saude)
- Respeitar preferencias (evitar alimentos que o cliente nao gosta)
- Este e um RASCUNHO para revisao profissional
- NAO prescrever suplementos
- NAO prometer resultados
- Retornar APENAS o rascunho alimentar, em portugues do Brasil"""


def gerar_dieta_base(db: Session, client_id: int) -> str:
    """Le onboarding do cliente, chama Anthropic e retorna rascunho de dieta (texto)."""
    import anthropic as anthropic_sdk

    dados = _buscar_onboarding(db, client_id)
    prefs = _extrair_preferencias(dados.get("observacoes"))

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY nao configurada")

    client_ai = anthropic_sdk.Anthropic(api_key=api_key)
    decisao = decidir(dados)
    prompt = _montar_prompt(dados, prefs, decisao["diretriz"])

    try:
        message = client_ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        draft = message.content[0].text.strip()
    except Exception as e:
        logger.error(f"Erro ao gerar dieta base (client {client_id}): {e}")
        raise HTTPException(status_code=502, detail=f"Erro ao gerar dieta com IA: {str(e)}")

    if not draft:
        raise HTTPException(status_code=502, detail="IA retornou resposta vazia.")

    return draft
