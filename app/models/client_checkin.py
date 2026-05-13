from sqlalchemy import Column, Integer, String, Float, Text, DateTime, func
from core.database import Base


class ClientCheckin(Base):
    __tablename__ = "client_checkins"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, nullable=False, index=True)
    treinou = Column(String)
    seguiu_dieta = Column(String)
    peso = Column(Float)
    energia = Column(String)
    dificuldade = Column(Text)
    observacoes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())