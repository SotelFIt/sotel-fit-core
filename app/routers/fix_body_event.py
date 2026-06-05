path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/app/routers/body_analysis.py'
content = open(path, 'r', encoding='utf-8-sig').read()

# Adiciona verificação: só cria evento se não existe avaliação do mesmo dia
old = """    # timeline event
    try:
        db.execute(
            text(\"\"\"
                INSERT INTO timeline_events (client_id, event_type, title, description, icon, created_at)
                VALUES (:cid, 'body_assessment', 'Nova avaliacao corporal registrada', :desc, '📊', NOW())
            \"\"\"),
            {
                "cid": client_id,
                "desc": resumo,
            }
        )
    except Exception as e:
        logger.warning(f"Erro ao criar timeline event: {e}")"""

new = """    # timeline event — apenas uma vez por dia
    try:
        existing_today = db.execute(
            text(\"\"\"
                SELECT COUNT(*) FROM timeline_events
                WHERE client_id = :cid
                AND event_type = 'body_assessment'
                AND DATE(created_at) = CURRENT_DATE
            \"\"\"),
            {"cid": client_id}
        ).scalar() or 0
        if existing_today == 0:
            db.execute(
                text(\"\"\"
                    INSERT INTO timeline_events (client_id, event_type, title, description, icon, created_at)
                    VALUES (:cid, 'body_assessment', 'Nova avaliacao corporal registrada', :desc, '📊', NOW())
                \"\"\"),
                {
                    "cid": client_id,
                    "desc": resumo,
                }
            )
    except Exception as e:
        logger.warning(f"Erro ao criar timeline event: {e}")"""

content = content.replace(old, new, 1)
open(path, 'w', encoding='utf-8').write(content)
print('OK - body_assessment fix:', content.count('existing_today'))