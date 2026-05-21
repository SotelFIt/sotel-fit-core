from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from core.database import Base

class OperationalEvent(Base):
    __tablename__ = "operational_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True)
    severity = Column(String)
    message = Column(String)
    endpoint = Column(String, nullable=True)
    status_code = Column(Integer, nullable=True)
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
            "error_details": self.error_details,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
