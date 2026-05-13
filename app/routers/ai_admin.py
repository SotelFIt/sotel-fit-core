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