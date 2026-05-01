from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import verify_dual_auth
from services.subscription_service import update_all_subscriptions_status

router = APIRouter(prefix="/cron", tags=["cron"])

def require_admin(auth_client_id: int = Depends(verify_dual_auth)):
    if auth_client_id != 0:
        raise HTTPException(status_code=403, detail="Apenas admin pode executar cron jobs")
    return auth_client_id

@router.post("/check-subscriptions")
def check_subscriptions(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    result = update_all_subscriptions_status(db)
    return {"status": "ok", "total_checked": result["total_checked"], "total_updated": result["total_updated"]}
