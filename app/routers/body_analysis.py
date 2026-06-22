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
        CREATE TABLE IF NOT EXISTS client_body_assessments (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            gordura_min FLOAT,
            gordura_max FLOAT,
            massa_magra_min FLOAT,
            massa_magra_max FLOAT,
            classificacao TEXT,
            ponto_positivo TEXT,
            ponto_atencao TEXT,
            foco_atual TEXT,
            nivel_atual TEXT,
            resposta_corporal TEXT,
            gordura_estimada TEXT,
            resumo_cliente TEXT,
            analise_completa TEXT,
            photos_analyzed INTEGER DEFAULT 0,
            origem VARCHAR DEFAULT 'admin',
            is_latest BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))
    db.commit()


def _parse_gordura(s: str):
    if not s:
        return None, None
    import re
    m = re.search(r'(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)', s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m2 = re.search(r'(\d+(?:\.\d+)?)', s)
    if m2:
        v = float(m2.group(1))
        return v, v
    return None, None


def _days_info(created_at):
    from datetime import datetime, timezone, timedelta
    if created_at is None:
        return 0, None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    days_since = (datetime.now(timezone.utc) - created_at).days
    days_until = max(0, 15 - days_since)
    next_date = (created_at + timedelta(days=15)).strftime('%Y-%m-%d') if days_until > 0 else None
    return days_until, next_date


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
        return None


def _save_assessment(db: Session, client_id: int, analysis: dict, raw_text: str, photos_count: int):
    _ensure_table(db)

    gordura_min, gordura_max = _parse_gordura(analysis.get("gordura_estimada", ""))
    peso_row = db.execute(
        text("SELECT weight FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    peso = peso_row[0] if peso_row and peso_row[0] else None

    massa_magra_min = round(peso * (1 - (gordura_max or 0) / 100), 1) if peso and gordura_max else None
    massa_magra_max = round(peso * (1 - (gordura_min or 0) / 100), 1) if peso and gordura_min else None

    resumo = (
        f"Gordura estimada: {analysis.get('gordura_estimada', '-')}. "
        f"{analysis.get('classificacao', '')}. "
        f"Foco atual: {analysis.get('foco_atual', '-')}."
    )

    # marca anteriores como não latest
    db.execute(
        text("UPDATE client_body_assessments SET is_latest = FALSE WHERE client_id = :cid"),
        {"cid": client_id}
    )

    db.execute(
        text("""
            INSERT INTO client_body_assessments (
                client_id, gordura_min, gordura_max, massa_magra_min, massa_magra_max,
                classificacao, ponto_positivo, ponto_atencao, foco_atual,
                nivel_atual, resposta_corporal, gordura_estimada,
                resumo_cliente, analise_completa, photos_analyzed, origem, is_latest, created_at
            ) VALUES (
                :cid, :gmin, :gmax, :mmmin, :mmmax,
                :clas, :pos, :atc, :foco,
                :nivel, :resp, :gest,
                :resumo, :raw, :photos, 'admin', TRUE, NOW()
            )
        """),
        {
            "cid": client_id, "gmin": gordura_min, "gmax": gordura_max,
            "mmmin": massa_magra_min, "mmmax": massa_magra_max,
            "clas": analysis.get("classificacao"),
            "pos": analysis.get("ponto_positivo"),
            "atc": analysis.get("ponto_atencao"),
            "foco": analysis.get("foco_atual"),
            "nivel": analysis.get("nivel_atual"),
            "resp": analysis.get("resposta_corporal"),
            "gest": analysis.get("gordura_estimada"),
            "resumo": resumo,
            "raw": raw_text,
            "photos": photos_count,
        }
    )

    # timeline event — apenas uma vez por dia
    try:
        existing_today = db.execute(
            text("""
                SELECT COUNT(*) FROM timeline_events
                WHERE client_id = :cid
                AND event_type = 'body_assessment'
                AND DATE(created_at) = CURRENT_DATE
            """),
            {"cid": client_id}
        ).scalar() or 0
        if existing_today == 0:
            db.execute(
                text("""
                    INSERT INTO timeline_events (client_id, event_type, title, description, icon, created_at)
                    VALUES (:cid, 'body_assessment', 'Nova avaliacao corporal registrada', :desc, '📊', NOW())
                """),
                {
                    "cid": client_id,
                    "desc": resumo,
                }
            )
    except Exception as e:
        logger.warning(f"Erro ao criar timeline event: {e}")

    db.commit()


def _generate_and_save(db: Session, client_id: int) -> dict:
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

    # [C1] Guarda de conjunto completo - avaliacao exige front + back + lateral.
    # Mesma convencao do gatilho automatico _maybe_generate_assessment.
    _cats_rows = db.execute(
        text("SELECT DISTINCT category FROM client_photos WHERE client_id = :cid"),
        {"cid": client_id}
    ).fetchall()
    _cats = {r[0] for r in _cats_rows}
    _has_front = "front" in _cats
    _has_back = "back" in _cats
    _has_side = ("side_left" in _cats) or ("side_right" in _cats)
    if not (_has_front and _has_back and _has_side):
        raise HTTPException(
            status_code=400,
            detail="Avaliacao requer 3 fotos: frente, costas e lateral. Conjunto incompleto."
        )

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
                raw_bytes = resp.read()
            if raw_bytes[:8].startswith(b'\x89PNG'):
                media_type = "image/png"
            elif raw_bytes[:3] == b'\xff\xd8\xff':
                media_type = "image/jpeg"
            elif raw_bytes[:4] == b'RIFF' and raw_bytes[8:12] == b'WEBP':
                media_type = "image/webp"
            elif raw_bytes[:6] in (b'GIF87a', b'GIF89a'):
                media_type = "image/gif"
            else:
                media_type = "image/jpeg"
            image_data = base64.b64encode(raw_bytes).decode('utf-8')
            content_parts.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": image_data}
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

    _save_assessment(db, client_id, analysis, raw, photos_count)
    return {"analysis": analysis, "photos_analyzed": photos_count, "raw": raw}


# CLIENTE — apenas leitura
@router.get("/client/{client_id}")
def get_body_analysis_client(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_jwt_only),
):
    if auth_client_id != client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    _ensure_table(db)
    row = _get_latest(db, client_id)
    if not row:
        raise HTTPException(status_code=404, detail="Nenhuma avaliacao disponivel. Aguarde seu personal gerar a analise.")

    return {
        "client_id": client_id,
        "analysis": {
            "gordura_estimada": row[1],
            "classificacao": row[2],
            "ponto_positivo": row[3],
            "ponto_atencao": row[4],
            "foco_atual": row[5],
            "nivel_atual": row[6],
            "resposta_corporal": row[7],
        },
        "resumo": row[8],
        "gordura_min": row[10],
        "gordura_max": row[11],
        "massa_magra_min": row[12],
        "massa_magra_max": row[13],
        "updated_at": str(row[14]),
        "days_until_next": _days_info(row[14])[0],
        "next_available_at": _days_info(row[14])[1],
        "disclaimer": "Estimativa inteligente. Nao substitui exames clinicos."
    }


# CLIENTE — gera análise
@router.post("/client/{client_id}")
def generate_body_analysis_client(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_jwt_only),
):
    if auth_client_id != client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    _ensure_table(db)
    from datetime import datetime, timezone
    latest = _get_latest(db, client_id)
    if latest:
        last_date = latest[14]
        if last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - last_date).days
        if days_since < 15:
            raise HTTPException(
                status_code=429,
                detail=f"Proxima avaliacao disponivel em {15 - days_since} dias."
            )

    result = _generate_and_save(db, client_id)
    return {
        "client_id": client_id,
        "analysis": result["analysis"],
        "photos_analyzed": result["photos_analyzed"],
    }


# CLIENTE — gera análise
@router.post("/client/{client_id}")
def generate_body_analysis_client(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_jwt_only),
):
    if auth_client_id != client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    _ensure_table(db)
    from datetime import datetime, timezone
    latest = _get_latest(db, client_id)
    if latest:
        last_date = latest[14]
        if last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - last_date).days
        if days_since < 15:
            raise HTTPException(
                status_code=429,
                detail=f"Proxima avaliacao disponivel em {15 - days_since} dias."
            )

    result = _generate_and_save(db, client_id)
    return {
        "client_id": client_id,
        "analysis": result["analysis"],
        "photos_analyzed": result["photos_analyzed"],
    }


# ADMIN — gera e salva
@router.post("/admin/{client_id}")
def generate_body_analysis_admin(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth),
):
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin")

    _ensure_table(db)
    from datetime import datetime, timezone
    latest = _get_latest(db, client_id)
    if latest:
        last_date = latest[14]
        if last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - last_date).days
        if days_since < 15:
            raise HTTPException(
                status_code=429,
                detail=f"Proxima avaliacao disponivel em {15 - days_since} dias."
            )
    result = _generate_and_save(db, client_id)

    client_row = db.execute(
        text("SELECT name FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()

    return {
        "client_id": client_id,
        "client_name": client_row[0] if client_row else None,
        "analysis": result["analysis"],
        "analysis_raw": result["raw"],
        "photos_analyzed": result["photos_analyzed"],
        "generated_at": datetime.utcnow().isoformat(),
    }


# ADMIN — lê última salva
@router.get("/admin/{client_id}")
def get_body_analysis_admin(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth),
):
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin")

    _ensure_table(db)
    row = _get_latest(db, client_id)
    if not row:
        raise HTTPException(status_code=404, detail="Nenhuma analise gerada ainda.")

    return {
        "client_id": client_id,
        "analysis": {
            "gordura_estimada": row[1],
            "classificacao": row[2],
            "ponto_positivo": row[3],
            "ponto_atencao": row[4],
            "foco_atual": row[5],
            "nivel_atual": row[6],
            "resposta_corporal": row[7],
        },
        "analysis_raw": row[9],
        "gordura_min": row[10],
        "gordura_max": row[11],
        "massa_magra_min": row[12],
        "massa_magra_max": row[13],
       "updated_at": str(row[14]),
        "days_until_next": _days_info(row[14])[0],
        "next_available_at": _days_info(row[14])[1],
        "photos_analyzed": row[15],
    }


# HISTÓRICO
@router.get("/admin/{client_id}/history")
def get_body_analysis_history(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth),
):
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin")

    _ensure_table(db)
    rows = db.execute(
        text("""
            SELECT id, gordura_estimada, classificacao, gordura_min, gordura_max,
                   massa_magra_min, massa_magra_max, is_latest, created_at
            FROM client_body_assessments
            WHERE client_id = :cid
            ORDER BY created_at DESC LIMIT 20
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
