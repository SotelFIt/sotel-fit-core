from pydantic import BaseModel

class DecisionLogResponse(BaseModel):
    id: int
    client_id: int
    checkin_id: int
    decision: str
    status: str
    alerts: str
    summary: str

    class Config:
        from_attributes = True