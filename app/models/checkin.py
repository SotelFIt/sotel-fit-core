from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from core.database import Base

class Checkin(Base):
    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    
    week_label = Column(String, nullable=False)
    weight = Column(Float, nullable=False)
    
    diet_adherence = Column(String, nullable=False)
    training_adherence = Column(String, nullable=False)
    energy = Column(String, nullable=False)
    
    difficulties = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    
    client = relationship(
        "Client",
        back_populates="checkins",
    )
    
    decision_logs = relationship(
        "DecisionLog",
        back_populates="checkin",
        foreign_keys="DecisionLog.checkin_id",
        cascade="all, delete-orphan",
    )
