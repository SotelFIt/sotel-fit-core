from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import verify_dual_auth
from schemas.subscription import ActivateSubscriptionRequest, RenewSubscriptionRequest, SubscriptionResponse
from services.subscription_service import activate_subscription, renew_subscription, get_subscription, get_expiring_subscriptions, get_expired_subscriptions

router = APIRouter(prefix="/admin", tags=["admin"])

def require_admin(auth_client_id: int = Depends(verify_dual_auth)):
    if auth_client_id != 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas admin pode acessar este endpoint")
    return auth_client_id

@router.post("/clients/{client_id}/activate-subscription", response_model=SubscriptionResponse)
def activate(client_id: int, payload: ActivateSubscriptionRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    return activate_subscription(db=db, client_id=client_id, plan_type=payload.plan_type, payment_method=payload.payment_method, notes=payload.notes)

@router.post("/clients/{client_id}/renew-subscription", response_model=SubscriptionResponse)
def renew(client_id: int, payload: RenewSubscriptionRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    return renew_subscription(db=db, client_id=client_id, plan_type=payload.plan_type, payment_method=payload.payment_method, notes=payload.notes)

@router.get("/clients/{client_id}/subscription", response_model=SubscriptionResponse)
def get_sub(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    sub = get_subscription(db, client_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Assinatura nao encontrada")
    return sub

@router.get("/subscriptions/expiring")
def list_expiring(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    return get_expiring_subscriptions(db)

@router.get("/subscriptions/expired")
def list_expired(db: Session = Depends(get_db), _: int = Depends(require_admin)):
    return get_expired_subscriptions(db)
