from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Index
from datetime import datetime
from core.database import Base

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=False)
    objective = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)
    landbot_user_id = Column(String, unique=True, index=True, nullable=True)
    age = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("ix_client_email_active", "email", "is_active"),
        Index("ix_client_landbot", "landbot_user_id"),
    )
