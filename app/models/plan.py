from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from database import Base

class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    onboarding_id = Column(Integer, ForeignKey("onboarding.id"), nullable=False, index=True)
    
    training_plan = Column(Text, nullable=False)
    diet_plan = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # ✅ Relacionamento com Client
    client = relationship(
        "Client",
        back_populates="plans",
        foreign_keys=[client_id],
    )
    
    # ✅ Relacionamento com Onboarding
    onboarding = relationship(
        "Onboarding",
        foreign_keys=[onboarding_id],
    )
    
    # ✅ Relacionamento com PlanVersion
    versions = relationship(
        "PlanVersion",
        back_populates="source_plan",
        cascade="all, delete-orphan",
        foreign_keys="PlanVersion.source_plan_id",
    )