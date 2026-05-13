from sqlalchemy import Column, Integer, String, Text, DateTime, func
from core.database import Base


class ClientDiet(Base):
    __tablename__ = "client_diets"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, nullable=False, index=True)
    content = Column(Text)
    status = Column(String, default="active")
    created_at = Column(DateTime, server_default=func.now())