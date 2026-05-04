from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from core.database import Base

class DietVersion(Base):
    __tablename__ = "diet_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    source_diet_id = Column(Integer, ForeignKey("diets.id"), nullable=False, index=True)
    
    version_number = Column(Integer, nullable=False)
    snapshot_json = Column(JSON, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    client = relationship(
        "Client",
        back_populates="diet_versions",
        foreign_keys=[client_id],
    )
    
    source_diet = relationship(
        "Diet",
        back_populates="versions",
        foreign_keys=[source_diet_id],
    )
