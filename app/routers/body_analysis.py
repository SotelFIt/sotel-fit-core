import logging
import os
import json
import base64
import urllib.request
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.database import get_db
from core.security import verify_jwt_only, verify_dual_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/body-analysis", tags=["body-analysis"])


def _ensure_table(db: Session):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS client_body_analysis (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL UNIQUE,
            analysis_json TEXT NOT NULL,
            raw_text TEXT,
            photos_analyzed INTEGER DEFAULT 0,
            generated_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """))
    db.commit()


def _get_cached(db: Session, client_id: int):
    try:
        row = db.execute(
            text("SELECT analysis_json, raw_text, photos_analyzed, updated_at FROM client_body_analysis WHERE client_id = :cid"),
            {"cid": client_id}
        ).fetchone()
        return row
    except Exception:
        return None


def _save_cache(db: Session, client_id: int, analysis_json: dict, raw_text: str, photos_count: int):
    _ensure_table(db)
    existing = db.execute(
        text("SELECT id FROM client_body_analysis WHERE client_id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if existing:
        db.execute(
            text("""
                UPDATE client_body_analysis
                SET analysis_json = :aj, raw_text = :rt, photos_analyzed = :pa, updated_at = NOW()
                WHERE client_id = :cid
            """),
            {"aj": json.dumps(analysis_json), "rt": raw_text, "pa": photos_count, "cid": client_id}
        )
    else:
        db.execute(
            text("""
                INSERT INTO client_body_analysis (client_id, analysis_json, raw_text, photos_analyzed, generated_at, updated_at)
                VALUES (:cid, :aj, :rt, :pa, NOW(), NOW())
            """),
            {"cid": client_id, "aj": json.dumps(analysis_json), "rt": raw_text, "pa": photos_count}
        )
    db.commit()


def _generate_analysis(db: Session, client_id: int) -> dict:
    import anthropic as anthropic_sdk

    photos = db.execute(
        text("""
            SELECT category, image_url, weight, created_at
            FROM client_photos
            WHERE client_id = :cid
            ORDER BY created_at DESC
            LIMIT 4
        """),
        {"cid": client_id}
    ).fetchall()

    if not photos:
        raise HTTPException(status_code=400, detail="Nenhuma foto encontrada. O cliente precisa enviar fotos pelo app.")

    client_row = db.execute(
        text("SELECT name, weight, height FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()

    weight = photos[0][2] or (client_row[1] if client_row else None)
    height = client_row[2] if client_row else None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY nao configurada")

    client_ai = anthropic_sdk.Anthropic(api_key=api_key)

    content_parts = [{
        "type": "text",
        "text": f"""Analise as fotos corporais e retorne APENAS um JSON valido com exatamente estas 7 chaves:

{{
  "gordura_estimada": "ex: 22-26%",
  "classificacao": "frase curta e direta sobre composicao corporal",
  "nivel_atual": "classificacao do nivel fisico atual",
  "ponto_positivo": "principal ponto positivo do fisico",
  "ponto_atencao": "principal ponto de atencao",
  "resposta_corporal": "como o corpo tende a responder ao treino/dieta",
  "foco_atual": "foco principal recomendado agora"
}}

Peso: {weight or 'nao informado'} kg | Altura: {height or 'nao informado'} cm
Linguagem: direta, humana, motivadora. Maximo 15 palavras por campo.
Retorne APENAS o JSON, sem markdown, sem texto adicional."""
    }]

    for photo in photos[:3]:
        try:
            with urllib.request.urlopen(photo[1]) as resp:
                image_data = base64.b64encode(resp.read()).decode('utf-8')
            content_parts.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}
            })
        except Exception as e:
            logger.warning(f"Erro ao carregar imagem: {e}")

    message = client_ai.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": content_parts}]
    )

    raw = message.content[0].text.strip().replace('```json', '').replace('```', '').strip()
    analysis = json.loads(raw)
    photos_count = len([p for p in content_parts if p.get("type") == "image"])

    _save_cache(db, client_id, analysis, raw, photos_count)
    return {"analysis": analysis, "photos_analyzed": photos_count}


@router.get("/client/{client_id}")
def get_body_analysis_client(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_jwt_only),
):
    if auth_client_id != client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    _ensure_table(db)
    cached = _get_cached(db, client_id)
    if cached:
        try:
            analysis = json.loads(cached[0])
            return {
                "client_id": client_id,
                "analysis": analysis,
                "updated_at": str(cached[3]),
                "from_cache": True,
                "disclaimer": "Estimativa inteligente baseada em analise corporal. Nao substitui exames clinicos."
            }
        except Exception:
            pass

    result = _generate_analysis(db, client_id)
    return {
        "client_id": client_id,
        "analysis": result["analysis"],
        "from_cache": False,
        "disclaimer": "Estimativa inteligente baseada em analise corporal. Nao substitui exames clinicos."
    }


@router.post("/admin/{client_id}")
def generate_body_analysis_admin(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth),
):
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin")

    _ensure_table(db)
    result = _generate_analysis(db, client_id)

    client_row = db.execute(
        text("SELECT name FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()

    return {
        "client_id": client_id,
        "client_name": client_row[0] if client_row else None,
        "analysis": result["analysis"],
        "photos_analyzed": result["photos_analyzed"],
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/admin/{client_id}/cached")
def get_cached_analysis_admin(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth),
):
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin")

    _ensure_table(db)
    cached = _get_cached(db, client_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Nenhuma analise gerada ainda.")

    return {
        "client_id": client_id,
        "analysis_raw": cached[1],
        "photos_analyzed": cached[2],
        "updated_at": str(cached[3]),
    }