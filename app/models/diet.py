from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from core.database import Base

class Diet(Base):
    __tablename__ = "diets"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    onboarding_id = Column(Integer, ForeignKey("onboarding.id"), nullable=False, index=True)
    
    dietary_plan = Column(Text, nullable=False)
    observations = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    client = relationship(
        "Client",
        back_populates="diets",
        foreign_keys=[client_id],
    )
    
    onboarding = relationship(
        "Onboarding",
        foreign_keys=[onboarding_id],
    )
    
    versions = relationship(
        "DietVersion",
        back_populates="source_diet",
        cascade="all, delete-orphan",
        foreign_keys="DietVersion.source_diet_id",
    )
