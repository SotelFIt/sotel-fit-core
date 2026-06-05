path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/app/routers/body_analysis.py'
content = open(path, 'r', encoding='utf-8-sig').read()

new_endpoint = '''

# CLIENTE — histórico de avaliações
@router.get("/client/{client_id}/history")
def get_body_analysis_history_client(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_jwt_only),
):
    if auth_client_id != client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    _ensure_table(db)
    rows = db.execute(
        text("""
            SELECT id, gordura_estimada, classificacao, gordura_min, gordura_max,
                   massa_magra_min, massa_magra_max, is_latest, created_at
            FROM client_body_assessments
            WHERE client_id = :cid
            ORDER BY created_at ASC
        """),
        {"cid": client_id}
    ).fetchall()

    return [
        {
            "id": r[0], "gordura_estimada": r[1], "classificacao": r[2],
            "gordura_min": r[3], "gordura_max": r[4],
            "massa_magra_min": r[5], "massa_magra_max": r[6],
            "is_latest": r[7], "created_at": str(r[8])
        }
        for r in rows
    ]
'''

content = content + new_endpoint
open(path, 'w', encoding='utf-8').write(content)
print('OK')