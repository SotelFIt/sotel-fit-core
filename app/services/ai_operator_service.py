import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from services.ai_context_service import get_client_context, get_all_active_clients_summary

logger = logging.getLogger(__name__)

# Risk score thresholds
RISK_LOW = 30
RISK_MEDIUM = 60
RISK_HIGH = 80

_ENERGY_WEIGHTS = {
    "alta": 0,
    "boa": 0,
    "normal": 1,
    "baixa": 2,
    "muito baixa": 3,
    "péssima": 3,
    "pessima": 3,
}

_TREINOU_NO = {"nao", "não", "no", "false", "0"}
_DIETA_NO = {"nao", "não", "no", "false", "0"}


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _score_checkin_frequency(checkin_count: int) -> int:
    """Missing check-ins over 4 weeks is a strong dropout signal."""
    if checkin_count == 0:
        return 40
    if checkin_count == 1:
        return 20
    if checkin_count == 2:
        return 10
    return 0


def _score_training_adherence(checkins: list[dict]) -> int:
    if not checkins:
        return 15
    no_train = sum(1 for c in checkins if _normalize(c.get("treinou")) in _TREINOU_NO)
    ratio = no_train / len(checkins)
    if ratio >= 0.75:
        return 25
    if ratio >= 0.5:
        return 15
    if ratio >= 0.25:
        return 8
    return 0


def _score_diet_adherence(checkins: list[dict]) -> int:
    if not checkins:
        return 10
    no_diet = sum(1 for c in checkins if _normalize(c.get("seguiu_dieta")) in _DIETA_NO)
    ratio = no_diet / len(checkins)
    if ratio >= 0.75:
        return 15
    if ratio >= 0.5:
        return 8
    if ratio >= 0.25:
        return 4
    return 0


def _score_energy(checkins: list[dict]) -> int:
    if not checkins:
        return 5
    total = sum(_ENERGY_WEIGHTS.get(_normalize(c.get("energia")), 1) for c in checkins)
    avg = total / len(checkins)
    if avg >= 2.5:
        return 10
    if avg >= 1.5:
        return 5
    return 0


def _score_weight_trend(checkins: list[dict]) -> int:
    weights = [c["peso"] for c in checkins if c.get("peso") and c["peso"] > 0]
    if len(weights) < 3:
        return 0
    # Detect stall: max weight delta < 0.3kg over 3+ points
    span = max(weights) - min(weights)
    if span < 0.3:
        return 5
    return 0


def _score_subscription(subscription: Optional[dict]) -> int:
    if not subscription:
        return 0
    score = 0
    days = subscription.get("days_until_expiry")
    if days is not None:
        if days < 0:
            score += 20
        elif days <= 7:
            score += 10
        elif days <= 14:
            score += 5
    if subscription.get("payment_status") == "overdue":
        score += 15
    return score


def _score_missing_plan_or_diet(active_plan: Optional[dict], active_diet: Optional[dict]) -> int:
    score = 0
    if not active_plan or not active_plan.get("has_content"):
        score += 5
    if not active_diet or not active_diet.get("has_content"):
        score += 5
    return score


def _build_alerts(
    checkins: list[dict],
    subscription: Optional[dict],
    active_plan: Optional[dict],
    active_diet: Optional[dict],
    risk_score: int,
) -> list[str]:
    alerts = []

    if not checkins:
        alerts.append("Sem check-ins nos últimos 28 dias — risco de abandono.")
    elif len(checkins) == 1:
        alerts.append("Apenas 1 check-in nos últimos 28 dias — engajamento baixo.")

    no_train = sum(1 for c in checkins if _normalize(c.get("treinou")) in _TREINOU_NO)
    if checkins and no_train / len(checkins) >= 0.5:
        alerts.append(f"Não treinou em {no_train} de {len(checkins)} check-ins.")

    no_diet = sum(1 for c in checkins if _normalize(c.get("seguiu_dieta")) in _DIETA_NO)
    if checkins and no_diet / len(checkins) >= 0.5:
        alerts.append(f"Não seguiu a dieta em {no_diet} de {len(checkins)} check-ins.")

    if subscription:
        days = subscription.get("days_until_expiry")
        if days is not None and days < 0:
            alerts.append("Assinatura vencida.")
        elif days is not None and days <= 7:
            alerts.append(f"Assinatura vence em {days} dias.")
        if subscription.get("payment_status") == "overdue":
            alerts.append("Pagamento em atraso.")

    if not active_plan or not active_plan.get("has_content"):
        alerts.append("Cliente sem plano de treino ativo.")
    if not active_diet or not active_diet.get("has_content"):
        alerts.append("Cliente sem plano alimentar ativo.")

    return alerts


def _build_recommendations(alerts: list[str], risk_score: int, checkins: list[dict]) -> list[str]:
    recs = []

    if risk_score >= RISK_HIGH:
        recs.append("Contato urgente recomendado — risco alto de evasão.")
    elif risk_score >= RISK_MEDIUM:
        recs.append("Engajar cliente proativamente esta semana.")

    if any("sem check-in" in a.lower() or "1 check-in" in a.lower() for a in alerts):
        recs.append("Enviar lembrete de check-in via WhatsApp.")

    if any("não treinou" in a.lower() for a in alerts):
        recs.append("Revisar plano de treino — pode não ser adequado à rotina atual.")

    if any("não seguiu a dieta" in a.lower() for a in alerts):
        recs.append("Revisar plano alimentar — barreiras de adesão identificadas.")

    if any("vence em" in a.lower() or "vencida" in a.lower() for a in alerts):
        recs.append("Iniciar processo de renovação de assinatura.")

    if any("sem plano" in a.lower() for a in alerts):
        recs.append("Criar e publicar plano para o cliente.")

    return recs


def analyze_client(db: Session, client_id: int) -> dict:
    context = get_client_context(db, client_id)
    if not context:
        return {"error": "Cliente não encontrado", "client_id": client_id}

    checkins = context["checkins_last_28d"]
    subscription = context["subscription"]
    active_plan = context["active_plan"]
    active_diet = context["active_diet"]

    score = 0
    score += _score_checkin_frequency(len(checkins))
    score += _score_training_adherence(checkins)
    score += _score_diet_adherence(checkins)
    score += _score_energy(checkins)
    score += _score_weight_trend(checkins)
    score += _score_subscription(subscription)
    score += _score_missing_plan_or_diet(active_plan, active_diet)
    score = min(score, 100)

    if score >= RISK_HIGH:
        risk_level = "alto"
    elif score >= RISK_MEDIUM:
        risk_level = "médio"
    elif score >= RISK_LOW:
        risk_level = "baixo"
    else:
        risk_level = "mínimo"

    alerts = _build_alerts(checkins, subscription, active_plan, active_diet, score)
    recommendations = _build_recommendations(alerts, score, checkins)

    return {
        "client_id": client_id,
        "client_name": context["client"]["name"],
        "risk_score": score,
        "risk_level": risk_level,
        "checkin_count_28d": len(checkins),
        "alerts": alerts,
        "recommendations": recommendations,
        "context": context,
        "analyzed_at": datetime.utcnow().isoformat(),
    }


def analyze_all_clients(db: Session) -> dict:
    all_clients = get_all_active_clients_summary(db)

    results = []
    for c in all_clients:
        client_id = c["id"]
        checkin_row = db.execute(
            text(
                "SELECT COUNT(*) FROM client_checkins WHERE client_id = :cid AND created_at >= NOW() - INTERVAL '28 days'"
            ),
            {"cid": client_id}
        ).scalar()

        days = c.get("days_until_expiry")

        # Lightweight risk scoring for list view (no full context load)
        score = 0
        if checkin_row == 0:
            score += 40
        elif checkin_row == 1:
            score += 20
        elif checkin_row == 2:
            score += 10

        if days is not None and days < 0:
            score += 20
        elif days is not None and days <= 7:
            score += 10

        if c.get("payment_status") == "overdue":
            score += 15

        score = min(score, 100)

        if score >= RISK_HIGH:
            risk_level = "alto"
        elif score >= RISK_MEDIUM:
            risk_level = "médio"
        elif score >= RISK_LOW:
            risk_level = "baixo"
        else:
            risk_level = "mínimo"

        results.append({
            "client_id": client_id,
            "client_name": c["name"],
            "phone": c["phone"],
            "status": c["status"],
            "sub_status": c["sub_status"],
            "days_until_expiry": days,
            "payment_status": c["payment_status"],
            "checkin_count_28d": checkin_row or 0,
            "risk_score": score,
            "risk_level": risk_level,
        })

    results.sort(key=lambda x: x["risk_score"], reverse=True)

    high_risk = [r for r in results if r["risk_score"] >= RISK_HIGH]
    medium_risk = [r for r in results if RISK_MEDIUM <= r["risk_score"] < RISK_HIGH]
    low_risk = [r for r in results if r["risk_score"] < RISK_MEDIUM]

    return {
        "total_clients": len(results),
        "high_risk_count": len(high_risk),
        "medium_risk_count": len(medium_risk),
        "low_risk_count": len(low_risk),
        "clients_by_risk": results,
        "analyzed_at": datetime.utcnow().isoformat(),
    }
