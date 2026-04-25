from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, List, Optional


class PlanVersionResponse(BaseModel):
    id: int
    plan_id: int
    client_id: int
    version_number: int
    snapshot_data: Dict[str, Any]
    trigger_type: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PlanVersionListResponse(BaseModel):
    items: List[PlanVersionResponse]