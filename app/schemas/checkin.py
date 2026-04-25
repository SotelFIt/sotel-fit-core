from pydantic import BaseModel

class CheckinCreate(BaseModel):
    client_id: int
    week_label: str
    weight: float
    diet_adherence: str
    training_adherence: str
    energy: str
    difficulties: str
    notes: str

class CheckinResponse(CheckinCreate):
    id: int

    class Config:
        from_attributes = True