from pydantic import BaseModel

class OnboardingCreate(BaseModel):
    client_id: int
    main_goal: str
    training_level: str
    injuries: str
    routine: str
    current_eating: str
    difficulties: str
    motivation: str

class OnboardingResponse(BaseModel):
    id: int
    client_id: int
    main_goal: str
    training_level: str
    injuries: str
    routine: str
    current_eating: str
    difficulties: str
    motivation: str

    class Config:
        from_attributes = True