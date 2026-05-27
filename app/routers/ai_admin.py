import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.database import get_db
from routers.admin import require_admin
from services.ai_operator_service import analyze_client, analyze_all_clients

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-admin", tags=["ai-admin"])


@router.get("/clients/at-risk")
def get_clients_at_risk(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return analyze_all_clients(db)


@router.get("/summary")
def get_operational_summary(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    data = analyze_all_clients(db)
    return {
        "summary": {
            "total_clients": data["total_clients"],
            "high_risk_count": data["high_risk_count"],
            "medium_risk_count": data["medium_risk_count"],
            "low_risk_count": data["low_risk_count"],
        },
        "high_risk_clients": [
            c for c in data["clients_by_risk"] if c["risk_level"] == "alto"
        ],
        "analyzed_at": data["analyzed_at"],
    }


@router.get("/clients/{client_id}/analysis")
def get_client_analysis(
    client_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    result = analyze_client(db, client_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/clients/{client_id}/checkin-summary")
def checkin_summary(
    client_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    row = db.execute(
        text("SELECT id, name FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")

    client_name = row[1]

    rows = db.execute(
        text("""
            SELECT treinou, seguiu_dieta, energia, peso, dificuldade, observacoes, created_at
            FROM client_checkins
            WHERE client_id = :cid
            ORDER BY created_at DESC
            LIMIT 12
        """),
        {"cid": client_id}
    ).fetchall()

    if not rows:
        return {
            "client_id": client_id,
            "client_name": client_name,
            "summary": f"{client_name} ainda nao realizou nenhum check-in. Recomenda-se entrar em contato para iniciar o acompanhamento.",
            "total_checkins": 0,
            "generated_at": datetime.utcnow().isoformat(),
        }

    total = len(rows)
    treinou_vals = [int(r[0]) for r in rows if r[0] and str(r[0]).isdigit()]
    dieta_vals = [int(r[1]) for r in rows if r[1] and str(r[1]).isdigit()]
    energia_vals = [int(r[2]) for r in rows if r[2] and str(r[2]).isdigit()]
    pesos = [r[3] for r in rows if r[3]]
    dificuldades = [r[4] for r in rows if r[4]]
    observacoes = [r[5] for r in rows if r[5]]

    def label(avg):
        if avg >= 4.5: return "excelente"
        if avg >= 3.5: return "boa"
        if avg >= 2.5: return "regular"
        return "baixa"

    lines = [f"Resumo de {client_name}: {total} check-in(s) registrado(s)."]

    if treinou_vals:
        avg = sum(treinou_vals) / len(treinou_vals)
        lines.append(f"Adesao ao treino: {label(avg)} (media {avg:.1f}/5).")

    if dieta_vals:
        avg = sum(dieta_vals) / len(dieta_vals)
        lines.append(f"Adesao a dieta: {label(avg)} (media {avg:.1f}/5).")

    if energia_vals:
        avg = sum(energia_vals) / len(energia_vals)
        lines.append(f"Energia relatada: {label(avg)} (media {avg:.1f}/5).")

    if pesos and len(pesos) >= 2:
        delta = pesos[0] - pesos[-1]
        if abs(delta) > 0.5:
            direction = "perdeu" if delta < 0 else "ganhou"
            lines.append(f"Variacao de peso: {direction} {abs(delta):.1f} kg no periodo.")

    if dificuldades:
        lines.append(f"Principal dificuldade: {str(dificuldades[0])}.")

    if observacoes:
        lines.append(f"Ultima observacao: {str(observacoes[0])[:120]}.")

    if treinou_vals and sum(treinou_vals) / len(treinou_vals) < 3:
        lines.append("Atencao: adesao ao treino abaixo do esperado - considere revisar o plano.")
    elif dieta_vals and sum(dieta_vals) / len(dieta_vals) < 3:
        lines.append("Atencao: adesao a dieta abaixo do esperado - considere ajustar o cardapio.")
    else:
        lines.append("Adesao geral satisfatoria. Manter acompanhamento regular.")

    return {
        "client_id": client_id,
        "client_name": client_name,
        "summary": " ".join(lines),
        "total_checkins": total,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/clients/{client_id}/retention-message")
def retention_message(
    client_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    row = db.execute(
        text("SELECT id, name, objective, weight FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")

    client_name = row[1]
    objective = row[2] or "seu objetivo"
    weight = row[3]

    since = datetime.utcnow() - timedelta(days=28)
    rows = db.execute(
        text("""
            SELECT treinou, seguiu_dieta, energia, peso, dificuldade, observacoes, created_at
            FROM client_checkins
            WHERE client_id = :cid AND created_at >= :since
            ORDER BY created_at DESC
        """),
        {"cid": client_id, "since": since}
    ).fetchall()

    checkin_count = len(rows)
    first_name = client_name.split()[0]

    treinou_vals = [int(r[0]) for r in rows if r[0] and str(r[0]).isdigit()]
    dieta_vals = [int(r[1]) for r in rows if r[1] and str(r[1]).isdigit()]
    dificuldades = [r[4] for r in rows if r[4]]
    pesos = [r[3] for r in rows if r[3]]

    avg_treino = sum(treinou_vals) / len(treinou_vals) if treinou_vals else None
    avg_dieta = sum(dieta_vals) / len(dieta_vals) if dieta_vals else None

    # Gerar mensagem baseada no perfil
    if checkin_count == 0:
        message = (
            f"Oi {first_name}! Tudo bem?\n\n"
            f"Percebi que faz um tempo que nao recebo seu check-in por aqui. "
            f"Como esta indo com {objective}?\n\n"
            f"Me manda um oi pra eu saber como voce esta. "
            f"Estou aqui pra te apoiar no que precisar!"
        )
    elif avg_treino is not None and avg_treino < 3:
        message = (
            f"Oi {first_name}! Passando pra dar um oi.\n\n"
            f"Vi pelo seu check-in que o treino tem sido um desafio ultimamente. "
            f"Isso e normal, todo mundo passa por fases assim.\n\n"
            f"Me conta o que tem dificultado mais — "
            f"posso ajustar o plano pra ficar mais facil de encaixar na sua rotina."
        )
    elif avg_dieta is not None and avg_dieta < 3:
        dif = f" Sobre {str(dificuldades[0]).lower()}, vamos pensar em alternativas juntos." if dificuldades else ""
        message = (
            f"Oi {first_name}! Como voce esta?\n\n"
            f"Notei que a alimentacao tem sido a parte mais desafiadora pra voce.{dif}\n\n"
            f"A dieta nao precisa ser perfeita, precisa ser sustentavel. "
            f"Me fala o que tem sido mais dificil que eu te ajudo a resolver!"
        )
    elif pesos and len(pesos) >= 2 and (pesos[0] - pesos[-1]) < -1:
        delta = abs(pesos[0] - pesos[-1])
        message = (
            f"Oi {first_name}! So passando pra parabenizar!\n\n"
            f"Voce ja perdeu {delta:.1f} kg desde que comecarmos a trabalhar juntos. "
            f"Isso e resultado de consistencia e dedicacao sua.\n\n"
            f"Continue assim! Qualquer duvida, me chama aqui."
        )
    else:
        message = (
            f"Oi {first_name}! Tudo bem?\n\n"
            f"So passando pra checar como voce esta indo com {objective}. "
            f"Seus check-ins mostram que voce esta no caminho certo.\n\n"
            f"Continua assim! Se tiver alguma duvida ou quiser ajustar algo no plano, me fala."
        )

    return {
        "client_id": client_id,
        "client_name": client_name,
        "message": message,
        "context": {
            "checkin_count_28d": checkin_count,
            "avg_treino": round(avg_treino, 1) if avg_treino else None,
            "avg_dieta": round(avg_dieta, 1) if avg_dieta else None,
        },
        "generated_at": datetime.utcnow().isoformat(),
    }
# ADICIONAR AO FINAL DO ai_admin.py

@router.get("/onboarding-analysis/{phone}")
def get_onboarding_analysis(
    phone: str,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    from models.lead_onboarding import LeadOnboarding
    import json
    import os
    import anthropic as anthropic_sdk

    phone_clean = phone.replace("whatsapp:", "")
    o = db.query(LeadOnboarding).filter(
        (LeadOnboarding.phone == phone) |
        (LeadOnboarding.phone == phone_clean) |
        (LeadOnboarding.phone == f"whatsapp:{phone_clean}")
    ).order_by(LeadOnboarding.created_at.desc()).first()

    if not o:
        raise HTTPException(status_code=404, detail="Onboarding nao encontrado")

    extra = {}
    if o.observacoes:
        try:
            extra = json.loads(o.observacoes)
        except Exception:
            pass

    context_str = f"""
Nome: {o.nome or '-'}
Idade: {o.idade or '-'}
Sexo: {extra.get('sexo', '-')}
Peso: {o.peso or '-'} kg
Altura: {o.altura or '-'} cm
Cidade: {extra.get('cidade', '-')}

OBJETIVO:
- Principal: {o.objetivo or '-'}
- Meta: {o.meta_principal or '-'}

EXPERIENCIA:
- Nivel: {o.nivel_treino or '-'}
- Treinou antes: {extra.get('treinou_antes', '-')}
- Tempo parado: {extra.get('tempo_parado', '-')}

ROTINA:
- Dias disponiveis: {o.dias_treino or '-'}
- Horario: {o.horario_treino or '-'}
- Tempo por treino: {extra.get('tempo_por_treino', '-')}
- Tipo de trabalho: {extra.get('tipo_trabalho', '-')}
- Nivel de estresse: {extra.get('nivel_estresse', '-')}
- Qualidade do sono: {extra.get('qualidade_sono', '-')}

SAUDE:
- Lesoes/restricoes: {o.lesoes or '-'}
- Dores frequentes: {extra.get('dores', '-')}
- Medicamentos: {extra.get('medicamentos', '-')}
- Problemas hormonais: {extra.get('problemas_hormonais', '-')}
- Problemas cardiacos: {extra.get('problemas_cardiacos', '-')}

ALIMENTACAO:
- Refeicoes por dia: {extra.get('refeicoes_dia', '-')}
- Consome alcool: {extra.get('consome_alcool', '-')}
- Hidratacao: {extra.get('bebe_agua', '-')}
- Compulsao alimentar: {extra.get('tem_compulsao', '-')}
- Maior dificuldade alimentar: {extra.get('dificuldade_alimentar', '-')}
- Alimentacao atual: {o.alimentacao_atual or '-'}

AMBIENTE:
- Local de treino: {extra.get('ambiente_treino', '-')}
- Equipamentos: {extra.get('tem_equipamentos', '-')}
- Cardio disponivel: {extra.get('cardio_disponivel', '-')}

COMPORTAMENTO:
- Principal impedimento: {extra.get('impedimento_principal', '-')}
- O que te faria desistir: {extra.get('motivo_desistencia', '-')}
- Expectativa: {extra.get('expectativa', '-')}
"""

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY nao configurada no Railway")

    try:
        client = anthropic_sdk.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": f"""Voce e um analista operacional especializado em personal training online.

Analise os dados do onboarding deste cliente e gere um relatorio operacional para o treinador.

DADOS DO CLIENTE:
{context_str}

Responda APENAS com JSON valido nesta estrutura exata (sem markdown, sem texto antes ou depois):
{{
  "resumo_operacional": "3-4 linhas resumindo o perfil completo para o treinador tomar decisao rapida",
  "classificacao": {{
    "perfil": "frase unica descrevendo o perfil comportamental",
    "comprometimento": "alto|medio|baixo",
    "risco_abandono": "alto|medio|baixo",
    "aderencia_provavel": "alta|media|baixa",
    "observacao": "explicacao breve da classificacao"
  }},
  "sugestao_treino": {{
    "divisao": "ex: ABC 4x semana",
    "frequencia": "ex: 4 dias por semana",
    "intensidade": "iniciante|moderada|alta",
    "foco": "ex: Hipertrofia com base aerobica",
    "observacoes": "pontos criticos para montagem do treino"
  }},
  "sugestao_dieta": {{
    "estrategia": "ex: Deficit moderado com proteina elevada",
    "distribuicao": "ex: 4 refeicoes com foco proteico",
    "foco": "ex: Proteina alta, carbo moderado, gordura boa",
    "observacoes": "consideracoes baseadas nas dificuldades relatadas"
  }},
  "insights": [
    "insight operacional 1",
    "insight operacional 2",
    "insight operacional 3",
    "insight operacional 4",
    "insight operacional 5"
  ]
}}"""
            }]
        )

        text_response = message.content[0].text.strip()
        if "```" in text_response:
            parts = text_response.split("```")
            text_response = parts[1] if len(parts) > 1 else text_response
            if text_response.startswith("json"):
                text_response = text_response[4:]

        analysis = json.loads(text_response.strip())

        return {
            "phone": phone,
            "client_name": o.nome,
            "analysis": analysis,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except json.JSONDecodeError as e:
        logger.error(f"Erro parse JSON da IA: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar resposta da IA")
    except Exception as e:
        logger.error(f"Erro na analise IA do onboarding: {e}")
        raise HTTPException(status_code=500, detail=str(e))