from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field

class ActivateSubscriptionRequest(BaseModel):
    plan_type: str = Field(..., description="monthly | quarterly | semiannual | annual")
    payment_method: str = Field(..., description="pix | card | cash | external_link | other")
    notes: Optional[str] = Field(None, max_length=500)

class RenewSubscriptionRequest(BaseModel):
    plan_type: str = Field(..., description="monthly | quarterly | semiannual | annual")
    payment_method: str = Field(..., description="pix | card | cash | external_link | other")
    notes: Optional[str] = Field(None, max_length=500)

class SubscriptionResponse(BaseModel):
    id: int
    client_id: int
    status: str
    plan_type: Optional[str]
    payment_status: str
    start_date: Optional[date]
    end_date: Optional[date]
    last_payment_date: Optional[date]
    next_payment_date: Optional[date]
    manual_payment_method: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
