from models.decision_log import DecisionLog

def apply_decision(db, client_id, checkin_id, analysis):

    decision = "manter"
    status = "ok"
    alerts = ""
    summary = ""

    # EXEMPLO DE REGRA
    if "baixa" in analysis["energy"] or "60%" in analysis["diet_adherence"]:
        decision = "ajustar plano"
        status = "alerta"
        alerts = "Baixa aderência ou energia"
        summary = "Cliente com dificuldade de consistência"

    # 👇 AQUI É O QUE FALTAVA
    log = DecisionLog(
        client_id=client_id,
        checkin_id=checkin_id,
        decision=decision,
        status=status,
        alerts=alerts,
        summary=summary
    )

    db.add(log)
    db.commit()
    db.refresh(log)

    return log