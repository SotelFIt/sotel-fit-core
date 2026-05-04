from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from core.database import Base

class PlanVersion(Base):
    __tablename__ = "plan_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    source_plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False, index=True)
    
    version_number = Column(Integer, nullable=False)
    snapshot_json = Column(JSON, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    client = relationship(
        "Client",
        back_populates="plan_versions",
        foreign_keys=[client_id],
    )
    
    source_plan = relationship(
        "Plan",
        back_populates="versions",
        foreign_keys=[source_plan_id],
    )
