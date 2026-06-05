path = 'app/routers/body_analysis.py'
content = open(path, 'r', encoding='utf-8').read()

# Remove o bloco errado que ficou dentro de _days_info
old = '''    return days_until, next_date
    try:
        return db.execute(
            text("""
                SELECT id, gordura_estimada, classificacao, ponto_positivo, ponto_atencao,
                       foco_atual, nivel_atual, resposta_corporal, resumo_cliente,
                       analise_completa, gordura_min, gordura_max,
                       massa_magra_min, massa_magra_max, created_at, photos_analyzed
                FROM client_body_assessments
                WHERE client_id = :cid AND is_latest = TRUE
                ORDER BY created_at DESC LIMIT 1
            """),
            {"cid": client_id}
        ).fetchone()
    except Exception:
        return None'''

new = '''    return days_until, next_date


def _get_latest(db, client_id):
    try:
        return db.execute(
            text("""
                SELECT id, gordura_estimada, classificacao, ponto_positivo, ponto_atencao,
                       foco_atual, nivel_atual, resposta_corporal, resumo_cliente,
                       analise_completa, gordura_min, gordura_max,
                       massa_magra_min, massa_magra_max, created_at, photos_analyzed
                FROM client_body_assessments
                WHERE client_id = :cid AND is_latest = TRUE
                ORDER BY created_at DESC LIMIT 1
            """),
            {"cid": client_id}
        ).fetchone()
    except Exception:
        return None'''

content = content.replace(old, new, 1)
open(path, 'w', encoding='utf-8').write(content)

# Verifica
c2 = open(path, 'r', encoding='utf-8').read()
lines = c2.split('\n')
for i, l in enumerate(lines, 1):
    if 'def _' in l:
        print(i, l)