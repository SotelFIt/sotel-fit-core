import logging
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/timeline", tags=["timeline"])


def create_event(db: Session, client_id: int, event_type: str, title: str,
                 description: str = None, icon: str = "⚡", metadata: dict = None):
    try:
        db.execute(
            text("""
                INSERT INTO timeline_events (client_id, event_type, title, description, icon, metadata, created_at)
                VALUES (:cid, :etype, :title, :desc, :icon, :meta, NOW())
            """),
            {
                "cid": client_id,
                "etype": event_type,
                "title": title,
                "desc": description,
                "icon": icon,
                "meta": json.dumps(metadata) if metadata else None,
            }
        )
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao criar timeline event: {e}")
        db.rollback()
        return False


@router.get("/client/{client_id}")
def get_timeline(client_id: int, limit: int = 20, db: Session = Depends(get_db)):
    try:
        rows = db.execute(
            text("""
                SELECT id, client_id, event_type, title, description, icon, metadata, created_at
                FROM timeline_events
                WHERE client_id = :cid
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"cid": client_id, "limit": limit}
        ).fetchall()
        return [
            {
                "id": r[0],
                "client_id": r[1],
                "event_type": r[2],
                "title": r[3],
                "description": r[4],
                "icon": r[5],
                "metadata": r[6],
                "created_at": str(r[7]),
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/event/{client_id}")
def manual_event(
    client_id: int,
    event_type: str,
    title: str,
    description: Optional[str] = None,
    icon: str = "⚡",
    db: Session = Depends(get_db),
):
    ok = create_event(db, client_id, event_type, title, description, icon)
    if not ok:
        raise HTTPException(status_code=500, detail="Erro ao criar evento")
    return {"status": "ok"}