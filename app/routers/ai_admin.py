import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.database import get_db
from core.security import verify_dual_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-admin", tags=["ai-admin"])


def require_admin(auth_client_id: int = Depends(verify_dual_auth)):
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin")
    return auth_client_id


def calculate_risk(client_id: int, client_name: str, db: Session) -> dict:
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
    risk_score = min(100, max(0, (4 - checkin_count) * 10))

    if risk_score >= 90:
        risk_level = "critico"
    elif risk_score >= 75:
        risk_level = "alto"
    elif risk_score >= 60:
        risk_level = "moderado"
    elif risk_score >= 30:
        risk_level = "baixo"
    else:
        risk_level = "minimo"

    alerts = []
    recommendations = []

    if checkin_count == 0:
        alerts.append("Nenhum check-in nos ultimos 28 dias")
        recommendations.append("Entrar em contato pelo WhatsApp para reengajar")
    elif checkin_count <= 2:
        alerts.append(f"Baixa frequencia de check-in: {checkin_count} em 28 dias")
        recommendations.append("Reforcar importancia do check-in semanal")

    if rows:
        treinou_vals = [int(r[0]) for r in rows if r[0] and str(r[0]).isdigit()]
        dieta_vals = [int(r[1]) for r in rows if r[1] and str(r[1]).isdigit()]
        energia_vals = [int(r[2]) for r in rows if r[2] and str(r[2]).isdigit()]

        if treinou_vals:
            avg = sum(treinou_vals) / len(treinou_vals)
            if avg < 3:
                alerts.append(f"Adesao ao treino baixa: media {avg:.1f}/5")
                recommendations.append("Revisar volume ou horario de treino")

        if dieta_vals:
            avg = sum(dieta_vals) / len(dieta_vals)
            if avg < 3:
                alerts.append(f"Adesao a dieta baixa: media {avg:.1f}/5")
                recommendations.append("Revisar plano alimentar")

        if energia_vals:
            avg = sum(energia_vals) / len(energia_vals)
            if avg < 3:
                alerts.append(f"Energia relatada baixa: media {avg:.1f}/5")
                recommendations.append("Verificar qualidade do sono e alimentacao")

        dificuldades = [r[4] for r in rows if r[4]]
        if dificuldades:
            alerts.append(f"Dificuldade relatada: {str(dificuldades[0])[:80]}")

    if not alerts:
        recommendations.append("Cliente com boa adesao - manter acompanhamento regular")

    return {
        "client_id": client_id,
        "client_name": client_name,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "checkin_count_28d": checkin_count,
        "alerts": alerts,
        "recommendations": recommendations,
        "analyzed_at": datetime.utcnow().isoformat(),
    }


@router.get("/clients/at-risk")
def clients_at_risk(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    clients = db.execute(
        text("SELECT id, name FROM clients ORDER BY created_at DESC")
    ).fetchall()
    results = [calculate_risk(c[0], c[1], db) for c in clients]
    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return results


@router.get("/summary")
def get_summary(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    clients = db.execute(
        text("SELECT id, name FROM clients ORDER BY created_at DESC")
    ).fetchall()
    results = [calculate_risk(c[0], c[1], db) for c in clients]
    high = [r for r in results if r["risk_score"] >= 75]
    medium = [r for r in results if 60 <= r["risk_score"] < 75]
    low = [r for r in results if r["risk_score"] < 60]
    return {
        "summary": {
            "total_clients": len(results),
            "high_risk_count": len(high),
            "medium_risk_count": len(medium),
            "low_risk_count": len(low),
        },
        "high_risk_clients": high,
        "analyzed_at": datetime.utcnow().isoformat(),
    }


@router.get("/clients/{client_id}/analysis")
def analyze_client(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    row = db.execute(
        text("SELECT id, name FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return calculate_risk(row[0], row[1], db)


@router.get("/clients/{client_id}/checkin-summary")
def checkin_summary(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
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

    if treinou_vals and sum(treinou_vals)/len(treinou_vals) < 3:
        lines.append("Atencao: adesao ao treino abaixo do esperado - considere revisar o plano.")
    elif dieta_vals and sum(dieta_vals)/len(dieta_vals) < 3:
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