import logging
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from core.database import get_db
from core.security import verify_jwt_only, verify_dual_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/photos", tags=["photos"])

VALID_CATEGORIES = {"front", "back", "side_right", "side_left"}


def require_admin(auth_client_id: int = Depends(verify_dual_auth)):
    if auth_client_id not in {0, 2}:
        raise HTTPException(status_code=403, detail="Apenas admin")
    return auth_client_id


@router.get("/debug/init")
def debug_init(db: Session = Depends(get_db)):
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS client_photos (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL,
                category VARCHAR NOT NULL,
                image_url TEXT NOT NULL,
                public_id VARCHAR,
                weight FLOAT,
                observation TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        db.commit()
        result = db.execute(text("SELECT COUNT(*) FROM client_photos")).fetchone()
        return {"status": "ok", "table": "client_photos", "rows": result[0]}
    except Exception as e:
        return {"error": str(e)}


@router.post("/upload/{client_id}")
async def upload_photo(
    client_id: int,
    category: str = Form(...),
    weight: Optional[float] = Form(None),
    observation: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth: int = Depends(verify_jwt_only),
):
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Categoria invalida. Use: {', '.join(VALID_CATEGORIES)}")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Apenas imagens sao aceitas")

    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True
        )
        contents = await file.read()
        result = cloudinary.uploader.upload(
            contents,
            folder=f"sotelfit/clients/{client_id}",
            public_id=f"{category}_{int(__import__('time').time())}",
            resource_type="image",
            transformation=[
                {"width": 1080, "height": 1920, "crop": "limit"},
                {"quality": "auto"},
                {"fetch_format": "auto"},
            ]
        )
        image_url = result.get("secure_url")
        public_id = result.get("public_id")
    except ImportError:
        raise HTTPException(status_code=500, detail="Cloudinary nao instalado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro upload: {str(e)}")

    try:
        db.execute(
            text("""
                INSERT INTO client_photos (client_id, category, image_url, public_id, weight, observation, created_at)
                VALUES (:cid, :category, :url, :public_id, :weight, :observation, NOW())
            """),
            {"cid": client_id, "category": category, "url": image_url,
             "public_id": public_id, "weight": weight, "observation": observation}
        )
        db.commit()
        return {"status": "ok", "image_url": image_url, "category": category, "client_id": client_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client/{client_id}")
def list_photos(client_id: int, db: Session = Depends(get_db)):
    try:
        rows = db.execute(
            text("""
                SELECT id, client_id, category, image_url, weight, observation, created_at
                FROM client_photos WHERE client_id = :cid ORDER BY created_at DESC
            """),
            {"cid": client_id}
        ).fetchall()
        return [{"id": r[0], "client_id": r[1], "category": r[2], "image_url": r[3],
                 "weight": r[4], "observation": r[5], "created_at": str(r[6])} for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client/{client_id}/by-date")
def list_photos_by_date(client_id: int, db: Session = Depends(get_db)):
    try:
        rows = db.execute(
            text("""
                SELECT id, client_id, category, image_url, weight, observation, created_at
                FROM client_photos WHERE client_id = :cid ORDER BY created_at DESC
            """),
            {"cid": client_id}
        ).fetchall()
        grouped = {}
        for r in rows:
            date_key = str(r[6])[:10]
            if date_key not in grouped:
                grouped[date_key] = {"date": date_key, "weight": r[4], "photos": []}
            grouped[date_key]["photos"].append({
                "id": r[0], "category": r[2], "image_url": r[3], "observation": r[5]
            })
        return list(grouped.values())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/photo/{photo_id}")
def delete_photo(photo_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    row = db.execute(
        text("SELECT public_id FROM client_photos WHERE id = :pid"),
        {"pid": photo_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Foto nao encontrada")
    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True
        )
        if row[0]:
            cloudinary.uploader.destroy(row[0])
    except Exception as e:
        logger.warning(f"Erro ao deletar do Cloudinary: {e}")
    db.execute(text("DELETE FROM client_photos WHERE id = :pid"), {"pid": photo_id})
    db.commit()
    return {"status": "ok", "message": "Foto removida"}