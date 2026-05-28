# clients router v2 - usa client_plans e client_diets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from core.database import get_db
from core.security import verify_dual_auth, verify_jwt_only
from services.client_service import get_or_create_client_from_phone, normalize_phone

router = APIRouter(prefix="/clients", tags=["clients"])


class CreateClientRequest(BaseModel):
    name: str
    email: str
    phone: str
    objective: str
    difficulty: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None


@router.get("/by-phone/{phone}")
def get_client_by_phone(phone: str, db: Session = Depends(get_db)):
    normalized = normalize_phone(phone)
    row = db.execute(
        text("SELECT id, name, email, phone, objective, status, created_at FROM clients WHERE phone = :p LIMIT 1"),
        {"p": normalized}
    ).fetchone()
    if row:
        return {"id": row[0], "name": row[1], "email": row[2], "phone": row[3], "objective": row[4], "status": row[5], "created_at": str(row[6])}
    cs = db.execute(
        text("SELECT phone, name FROM conversation_states WHERE phone = :p LIMIT 1"),
        {"p": normalized}
    ).fetchone()
    if cs:
        client = get_or_create_client_from_phone(db, cs[0], cs[1])
        return {"id": client["id"], "name": client["name"], "email": None, "phone": client["phone"], "objective": client["objective"], "status": client["status"], "created_at": None}
    raise HTTPException(status_code=404, detail="Cliente nao encontrado")


@router.get("/by-phone/{phone}/data")
def get_client_data(phone: str, db: Session = Depends(get_db)):
    normalized = normalize_phone(phone)
    client = db.execute(
        text("SELECT id, name, email, phone, objective, status FROM clients WHERE phone = :p LIMIT 1"),
        {"p": normalized}
    ).fetchone()
    if not client:
        cs = db.execute(
            text("SELECT phone, name FROM conversation_states WHERE phone = :p LIMIT 1"),
            {"p": normalized}
        ).fetchone()
        if cs:
            created = get_or_create_client_from_phone(db, cs[0], cs[1])
            client_id = created["id"]
            client_info = created
        else:
            raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    else:
        client_id = client[0]
        client_info = {"id": client[0], "name": client[1], "email": client[2], "phone": client[3], "objective": client[4], "status": client[5]}

    ob = db.execute(
        text("SELECT nome, objetivo, nivel_treino, dias_treino, meta_principal FROM lead_onboardings WHERE phone = :p ORDER BY created_at DESC LIMIT 1"),
        {"p": normalized}
    ).fetchone()

    plan = None
    try:
        plan = db.execute(
            text("SELECT id, content, created_at FROM client_plans WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
            {"cid": client_id}
        ).fetchone()
    except Exception:
        pass

    diet = None
    try:
        diet = db.execute(
            text("SELECT id, content, created_at FROM client_diets WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
            {"cid": client_id}
        ).fetchone()
    except Exception:
        pass

    return {
        "client": client_info,
        "onboarding": {"nome": ob[0], "objetivo": ob[1], "nivel_treino": ob[2], "dias_treino": ob[3], "meta_principal": ob[4]} if ob else None,
        "plan": {"id": plan[0], "content": plan[1], "created_at": str(plan[2])} if plan else None,
        "diet": {"id": diet[0], "content": diet[1], "created_at": str(diet[2])} if diet else None,
    }


@router.post("")
def create_client(payload: CreateClientRequest, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin")
    existing = db.execute(
        text("SELECT id FROM clients WHERE email = :email LIMIT 1"),
        {"email": payload.email}
    ).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Email ja cadastrado")
    result = db.execute(
        text("""
            INSERT INTO clients (name, email, phone, objective, age, weight, height, status, created_at)
            VALUES (:name, :email, :phone, :objective, :age, :weight, :height, 'active', NOW())
            RETURNING id, name, email, phone, objective, age, weight, height, status
        """),
        {
            "name": payload.name,
            "email": payload.email,
            "phone": payload.phone,
            "objective": payload.objective,
            "age": payload.age,
            "weight": payload.weight,
            "height": payload.height,
        }
    ).fetchone()
    db.commit()
    return {
        "id": result[0], "name": result[1], "email": result[2], "phone": result[3],
        "objective": result[4], "age": result[5], "weight": result[6],
        "height": result[7], "status": result[8], "difficulty": payload.difficulty
    }


@router.get("")
def list_clients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    if auth_client_id == 0:
        rows = db.execute(
            text("SELECT id, name, email, phone, objective, status, age, weight, height FROM clients WHERE status != 'inactive' ORDER BY created_at DESC LIMIT :limit OFFSET :skip"),
            {"limit": min(limit, 500), "skip": skip}
        ).fetchall()
    else:
        rows = db.execute(
            text("SELECT id, name, email, phone, objective, status, age, weight, height FROM clients WHERE id = :cid LIMIT 1"),
            {"cid": auth_client_id}
        ).fetchall()
    return [
        {"id": r[0], "name": r[1], "email": r[2], "phone": r[3], "objective": r[4],
         "status": r[5], "age": r[6], "weight": r[7], "height": r[8], "difficulty": None}
        for r in rows
    ]


@router.get("/{client_id}/plan")
def get_my_plan(client_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT content FROM client_plans WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
        {"cid": client_id}
    ).fetchone()
    return {"content": result[0] if result else ""}


@router.get("/{client_id}/diet")
def get_my_diet(client_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT content FROM client_diets WHERE client_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
        {"cid": client_id}
    ).fetchone()
    return {"content": result[0] if result else ""}

@router.get("/{client_id}")
def get_client(client_id: int, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    row = db.execute(
        text("SELECT id, name, email, phone, objective, status, age, weight, height FROM clients WHERE id = :cid LIMIT 1"),
        {"cid": client_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return {"id": row[0], "name": row[1], "email": row[2], "phone": row[3], "objective": row[4],
            "status": row[5], "age": row[6], "weight": row[7], "height": row[8], "difficulty": None}


@router.patch("/{client_id}")
def update_client(client_id: int, payload: dict, db: Session = Depends(get_db), auth_client_id: int = Depends(verify_dual_auth)):
    allowed = {"name", "email", "objective", "status"}
@router.get("/{client_id}/checkins")
def get_my_checkins(client_id: int, db: Session = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT id, client_id, treinou, seguiu_dieta, peso, energia, dificuldade, observacoes, created_at
            FROM client_checkins WHERE client_id = :cid ORDER BY created_at DESC LIMIT 30
        """),
        {"cid": client_id}
    ).fetchall()
    return [{"id": r[0], "client_id": r[1], "treinou": r[2], "seguiu_dieta": r[3],
             "peso": r[4], "energia": r[5], "dificuldade": r[6], "observacoes": r[7],
             "created_at": str(r[8])} for r in rows]
@router.get("/{client_id}/checkins")
def get_my_checkins(client_id: int, db: Session = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT id, client_id, treinou, seguiu_dieta, peso, energia, dificuldade, observacoes, created_at
            FROM client_checkins WHERE client_id = :cid ORDER BY created_at DESC LIMIT 30
        """),
        {"cid": client_id}
    ).fetchall()
    return [{"id": r[0], "client_id": r[1], "treinou": r[2], "seguiu_dieta": r[3],
             "peso": r[4], "energia": r[5], "dificuldade": r[6], "observacoes": r[7],
             "created_at": str(r[8])} for r in rows]
# ADICIONAR ao final de routers/clients.py (ou criar novo arquivo)
# Endpoint: GET /clients/{client_id}/body-analysis

@router.get("/{client_id}/body-analysis")
def get_client_body_analysis(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_jwt_only),
):
    import os
    import base64
    import urllib.request
    from sqlalchemy import text
    import anthropic as anthropic_sdk

    if auth_client_id != client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    # Get photos
    photos = db.execute(
        text("""
            SELECT category, image_url FROM client_photos
            WHERE client_id = :cid ORDER BY created_at DESC LIMIT 4
        """),
        {"cid": client_id}
    ).fetchall()

    if not photos:
        raise HTTPException(status_code=404, detail="Nenhuma foto encontrada. Envie fotos para gerar a análise.")

    # Get client data
    client_row = db.execute(
        text("SELECT name, weight, height FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()

    weight = client_row[1] if client_row else None
    height = client_row[2] if client_row else None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Configuração interna inválida")

    try:
        client_ai = anthropic_sdk.Anthropic(api_key=api_key)

        content_parts = []
        content_parts.append({
            "type": "text",
            "text": f"""Analise as fotos corporais e retorne APENAS um JSON válido com exatamente estas 7 chaves:

{{
  "gordura_estimada": "ex: 22-26%",
  "classificacao": "frase curta e direta sobre composição corporal",
  "nivel_atual": "classificação do nível físico atual",
  "ponto_positivo": "principal ponto positivo do físico",
  "ponto_atencao": "principal ponto de atenção",
  "resposta_corporal": "como o corpo tende a responder ao treino/dieta",
  "foco_atual": "foco principal recomendado agora"
}}

Peso: {weight or 'não informado'} kg | Altura: {height or 'não informado'} cm
Linguagem: direta, humana, motivadora. Máximo 15 palavras por campo.
Retorne APENAS o JSON, sem markdown, sem texto adicional."""
        })

        for photo in photos[:3]:
            image_url = photo[1]
            try:
                with urllib.request.urlopen(image_url) as resp:
                    image_data = base64.b64encode(resp.read()).decode('utf-8')
                content_parts.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}
                })
            except Exception:
                pass

        message = client_ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": content_parts}]
        )

        import json
        raw = message.content[0].text.strip()
        raw = raw.replace('```json', '').replace('```', '').strip()
        analysis = json.loads(raw)

        return {
            "client_id": client_id,
            "analysis": analysis,
            "disclaimer": "Estimativa inteligente baseada em análise corporal. Não substitui exames clínicos.",
            "has_photos": len(photos)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na análise: {str(e)}")