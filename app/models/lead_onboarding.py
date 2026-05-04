from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from core.database import Base

class LeadOnboarding(Base):
    __tablename__ = "lead_onboardings"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, nullable=True, index=True)
    nome = Column(String, nullable=True)
    email = Column(String, nullable=True)
    telefone = Column(String, nullable=True)
    idade = Column(String, nullable=True)
    peso = Column(String, nullable=True)
    altura = Column(String, nullable=True)
    objetivo = Column(String, nullable=True)
    nivel_treino = Column(String, nullable=True)
    dias_treino = Column(String, nullable=True)
    horario_treino = Column(String, nullable=True)
    lesoes = Column(String, nullable=True)
    alimentacao_atual = Column(String, nullable=True)
    maior_dificuldade = Column(String, nullable=True)
    meta_principal = Column(String, nullable=True)
    observacoes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())