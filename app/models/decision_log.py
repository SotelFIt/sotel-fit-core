from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from core.database import Base

class DecisionLog(Base):
    __tablename__ = "decision_logs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    checkin_id = Column(Integer, ForeignKey("checkins.id"), nullable=False, index=True)
    
    decision = Column(String, nullable=False)
    status = Column(String, nullable=False)
    alerts = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    client = relationship(
        "Client",
        back_populates="decision_logs",
        foreign_keys=[client_id],
    )
    
    checkin = relationship(
        "Checkin",
        back_populates="decision_logs",
        foreign_keys=[checkin_id],
    )
