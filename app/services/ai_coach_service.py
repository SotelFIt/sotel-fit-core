import json
import logging
import os

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _buscar_onboarding(db: Session, client_id: int) -> dict:
    client_row = db.execute(
        text("SELECT phone FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if not client_row or not client_row[0]:
        return {}
    phone = client_row[0]
    phone_clean = phone.replace("whatsapp:", "")
    o = db.execute(
        text("""
            SELECT objetivo, meta_principal, nivel_treino, dias_treino,
                   horario_treino, lesoes, peso, altura, idade,
                   alimentacao_atual, maior_dificuldade
            FROM lead_onboardings
            WHERE phone = :p OR phone = :pc OR phone = :pw
            ORDER BY created_at DESC LIMIT 1
        """),
        {"p": phone, "pc": phone_clean, "pw": f"whatsapp:{phone_clean}"}
    ).fetchone()
    if not o:
        return {}
    return {
        "objetivo": o[0], "meta_principal": o[1], "nivel_treino": o[2],
        "dias_treino": o[3], "horario_treino": o[4], "lesoes": o[5],
        "peso": o[6], "altura": o[7], "idade": o[8],
        "alimentacao_atual": o[9], "maior_dificuldade": o[10],
    }


def _buscar_checkins(db: Session, client_id: int) -> list:
    rows = db.execute(
        text("""
            SELECT treinou, seguiu_dieta, peso, energia, dificuldade,
                   observacoes, created_at
            FROM client_checkins
            WHERE client_id = :cid
            ORDER BY created_at DESC LIMIT 5
        """),
        {"cid": client_id}
    ).fetchall()
    return [
        {
            "treinou": r[0], "seguiu_dieta": r[1], "peso": r[2],
            "energia": r[3], "dificuldade": r[4], "observacoes": r[5],
            "created_at": str(r[6]) if r[6] else None,
        }
        for r in rows
    ]


def _buscar_avaliacao(db: Session, client_id: int) -> dict:
    atual = db.execute(
        text("""
            SELECT gordura_estimada, classificacao, foco_atual,
                   ponto_positivo, ponto_atencao, created_at
            FROM client_body_assessments
            WHERE client_id = :cid AND is_latest = TRUE LIMIT 1
        """),
        {"cid": client_id}
    ).fetchone()
    historico = db.execute(
        text("""
            SELECT gordura_estimada, classificacao, created_at
            FROM client_body_assessments
            WHERE client_id = :cid
            ORDER BY created_at DESC LIMIT 5
        """),
        {"cid": client_id}
    ).fetchall()
    return {
        "atual": {
            "gordura_estimada": atual[0], "classificacao": atual[1],
            "foco_atual": atual[2], "ponto_positivo": atual[3],
            "ponto_atencao": atual[4],
            "created_at": str(atual[5]) if atual[5] else None,
        } if atual else None,
        "historico": [
            {"gordura_estimada": h[0], "classificacao": h[1],
             "created_at": str(h[2]) if h[2] else None}
            for h in historico
        ],
    }


def _buscar_treino(db: Session, client_id: int) -> dict:
    r = db.execute(
        text("""
            SELECT content, created_at FROM client_plans
            WHERE client_id = :cid AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        """),
        {"cid": client_id}
    ).fetchone()
    if not r:
        return {}
    return {"content": r[0], "created_at": str(r[1]) if r[1] else None}


def _buscar_dieta(db: Session, client_id: int) -> dict:
    r = db.execute(
        text("""
            SELECT content, created_at FROM client_diets
            WHERE client_id = :cid AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        """),
        {"cid": client_id}
    ).fetchone()
    if not r:
        return {}
    return {"content": r[0], "created_at": str(r[1]) if r[1] else None}


def _resumir(texto, limite=600):
    if not texto:
        return "nao informado"
    texto = str(texto)
    return texto if len(texto) <= limite else texto[:limite] + "..."


def _montar_prompt(onb, checkins, aval, treino, dieta) -> str:
    linhas_ci = []
    for c in checkins:
        linhas_ci.append(
            f"- {c['created_at']}: treinou={c['treinou']}, "
            f"dieta={c['seguiu_dieta']}, energia={c['energia']}, "
            f"peso={c['peso']}, dificuldade={c['dificuldade'] or '-'}, "
            f"obs={c['observacoes'] or '-'}"
        )
    bloco_ci = "\n".join(linhas_ci) if linhas_ci else "Nenhum check-in registrado."
    total_ci = len(checkins)

    if aval and aval.get("atual"):
        a = aval["atual"]
        bloco_aval = (
            f"Atual ({a['created_at']}): gordura={a['gordura_estimada']}, "
            f"classificacao={a['classificacao']}, foco={a['foco_atual']}, "
            f"ponto_positivo={a['ponto_positivo']}, "
            f"ponto_atencao={a['ponto_atencao']}"
        )
        if aval.get("historico") and len(aval["historico"]) > 1:
            hist = "; ".join(
                f"{h['created_at']}: gordura={h['gordura_estimada']}"
                for h in aval["historico"]
            )
            bloco_aval += f"\nHistorico de gordura: {hist}"
    else:
        bloco_aval = "Nenhuma avaliacao corporal registrada."

    return f"""Voce e um assistente de acompanhamento para um personal trainer, gerando analise consultiva para revisao profissional. Voce NAO altera nada, apenas analisa.

[ONBOARDING]
Objetivo: {onb.get('objetivo') or 'nao informado'}
Meta principal: {onb.get('meta_principal') or 'nao informado'}
Nivel de treino: {onb.get('nivel_treino') or 'nao informado'}
Dias de treino: {onb.get('dias_treino') or 'nao informado'}
Lesoes: {onb.get('lesoes') or 'nenhuma informada'}
Peso/Altura/Idade: {onb.get('peso') or '?'} kg / {onb.get('altura') or '?'} cm / {onb.get('idade') or '?'} anos
Maior dificuldade: {onb.get('maior_dificuldade') or 'nao informado'}

[CHECK-INS] (total disponivel: {total_ci} | exibindo ultimos 5, do mais recente ao mais antigo)
ATENCAO: treinou, seguiu_dieta e energia usam escala 1-5 (5=otimo, 1=pessimo).
Check-ins antigos podem ter texto livre. Peso pode ser null.
{bloco_ci}

[AVALIACAO CORPORAL]
{bloco_aval}

[TREINO ATIVO]
{_resumir(treino.get('content'))}

[DIETA ATIVA]
{_resumir(dieta.get('content'))}

[TAREFA]
Analise a TENDENCIA do cliente ao longo dos check-ins, nao apenas o ultimo.
Cruze aderencia + energia + evolucao de peso + evolucao corporal.

Retorne APENAS um JSON valido com exatamente estas 7 chaves (sem markdown):
{{
  "summary": "resumo geral em 1-2 frases",
  "adherence": "Baixa, Moderada ou Alta + justificativa curta",
  "evolution": "o que esta acontecendo com o cliente",
  "bottleneck": "maior problema identificado",
  "opportunity": "sugestao de melhoria para o personal",
  "attention_level": "Baixo, Moderado, Alto ou Critico",
  "recommendation": "texto consultivo curto para o personal"
}}

REGRAS:
- Voce SUGERE, nunca decide. A decisao e sempre do personal.
- Nao prescrever medicamento ou suplemento. Nao prometer resultado.
- Se faltarem dados, diga isso honestamente no campo correspondente.
- Se houver menos de 3 check-ins (total_ci={total_ci}), NAO concluir tendencias.
  Informe que ainda nao ha dados suficientes para analise comportamental consistente.
- Responder em portugues do Brasil. APENAS o JSON."""


def gerar_insights(db: Session, client_id: int) -> dict:
    import anthropic as anthropic_sdk

    cliente = db.execute(
        text("SELECT id FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")

    onb = _buscar_onboarding(db, client_id)
    checkins = _buscar_checkins(db, client_id)
    aval = _buscar_avaliacao(db, client_id)
    treino = _buscar_treino(db, client_id)
    dieta = _buscar_dieta(db, client_id)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY nao configurada")

    client_ai = anthropic_sdk.Anthropic(api_key=api_key)
    prompt = _montar_prompt(onb, checkins, aval, treino, dieta)

    try:
        message = client_ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()
    except Exception as e:
        logger.error(f"Erro ao gerar insights (client {client_id}): {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao gerar analise com IA: {str(e)}"
        )

    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(cleaned)
    except Exception as e:
        logger.error(
            f"IA retornou JSON invalido (client {client_id}): {e} | raw={raw[:300]}"
        )
        raise HTTPException(
            status_code=502,
            detail="IA retornou resposta em formato invalido."
        )

    chaves = ["summary", "adherence", "evolution", "bottleneck",
              "opportunity", "attention_level", "recommendation"]
    return {k: data.get(k, "") for k in chaves}
