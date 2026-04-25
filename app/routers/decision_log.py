from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from schemas.decision_log import DecisionLogResponse
from services.decision_log_service import get_decision_logs_by_client
from database import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/clients/{client_id}/decision-logs", response_model=list[DecisionLogResponse])
def list_decision_logs(client_id: int, db: Session = Depends(get_db)):
    return get_decision_logs_by_client(db, client_id)