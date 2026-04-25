from pydantic import BaseModel

class DietCreate(BaseModel):
    client_id: int
    onboarding_id: int
    dietary_plan: str
    observations: str

class DietResponse(DietCreate):
    id: int

    class Config:
        from_attributes = True