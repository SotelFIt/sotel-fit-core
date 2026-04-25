from pydantic import BaseModel

class PlanCreate(BaseModel):
    client_id: int
    onboarding_id: int
    training_plan: str
    diet_plan: str
    notes: str

class PlanResponse(BaseModel):
    id: int
    client_id: int
    onboarding_id: int
    training_plan: str
    diet_plan: str
    notes: str

    class Config:
        from_attributes = True