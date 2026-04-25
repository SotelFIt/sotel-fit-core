from pydantic import BaseModel
from typing import Optional

class LandbotRequestSchema(BaseModel):
    landbot_user_id: str
    name: str
    phone: str
    email: str
    objective: str
    difficulty: str
    timestamp: Optional[str] = None
    
    class Config:
        from_attributes = True

class ClientResponseSchema(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    objective: str
    difficulty: str
    
    class Config:
        from_attributes = True
