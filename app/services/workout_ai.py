import logging
import os

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.metodo_sotel import decidir

logger = logging.getLogger(__name__)


def _buscar_onboarding(db: Session, client_id: int):
    """client_id -> telefone (clients) -> lead_onboardings (mesma logica de get_client_onboarding)."""
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
            SELECT objetivo, nivel_treino, dias_treino, horario_treino,
                   lesoes, peso, altura, idade, maior_dificuldade, meta_principal
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
            detail="Cliente ainda nao completou o onboarding. Nao ha dados para gerar o treino."
        )

    return {
        "objetivo": o[0],
        "nivel_treino": o[1],
        "dias_treino": o[2],
        "horario_treino": o[3],
        "lesoes": o[4],
        "peso": o[5],
        "altura": o[6],
        "idade": o[7],
        "maior_dificuldade": o[8],
        "meta_principal": o[9],
    }


def _montar_prompt(dados: dict, diretriz_sotel: str = "") -> str:
    return f"""Voce e um personal trainer especializado em consultoria online no Brasil.

Dados do cliente:
- Objetivo principal: {dados.get('objetivo') or 'nao informado'}
- Meta principal: {dados.get('meta_principal') or 'nao informado'}
- Nivel de experiencia: {dados.get('nivel_treino') or 'nao informado'}
- Dias disponiveis para treinar por semana: {dados.get('dias_treino') or 'nao informado'}
- Horario disponivel: {dados.get('horario_treino') or 'nao informado'}
- Lesoes ou restricoes fisicas: {dados.get('lesoes') or 'nenhuma informada'}
- Maior dificuldade: {dados.get('maior_dificuldade') or 'nao informado'}
- Peso: {dados.get('peso') or 'nao informado'} kg | Altura: {dados.get('altura') or 'nao informado'} cm

DIRETRIZ ESTRATEGICA DO METODO SOTEL (seguir obrigatoriamente):
{diretriz_sotel}

Gere um rascunho de treino semanal estruturado para este cliente, RESPEITANDO a diretriz estrategica acima.

FORMATO OBRIGATORIO:
- Dividir por dias (Treino A, Treino B, etc.), respeitando os dias disponiveis
- Cada exercicio com: series x repeticoes + tempo de descanso
- Observacoes de execucao onde necessario
- Maximo 600 palavras

REGRAS:
- Este e um RASCUNHO para o personal trainer revisar e ajustar
- Nao fazer prescricao para lesoes — apenas indicar cautela
- Ser conservador em casos de restricao fisica
- NAO gerar plano alimentar. NAO mencionar dieta.
- Responder em portugues do Brasil."""


def gerar_treino_base(db: Session, client_id: int) -> str:
    """Le onboarding do cliente, chama Anthropic e retorna rascunho de treino (texto)."""
    import anthropic as anthropic_sdk

    dados = _buscar_onboarding(db, client_id)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY nao configurada")

    client_ai = anthropic_sdk.Anthropic(api_key=api_key)

    decisao = decidir(dados)
    prompt = _montar_prompt(dados, decisao["diretriz"])

    try:
        message = client_ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        draft = message.content[0].text.strip()
    except Exception as e:
        logger.error(f"Erro ao gerar treino base (client {client_id}): {e}")
        raise HTTPException(status_code=502, detail=f"Erro ao gerar treino com IA: {str(e)}")

    if not draft:
        raise HTTPException(status_code=502, detail="IA retornou resposta vazia.")

    return draft
