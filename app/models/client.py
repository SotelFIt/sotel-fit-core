from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Float
from sqlalchemy.orm import relationship
from core.database import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True, index=True)
    objective = Column(String, nullable=True)
    difficulty = Column(String, nullable=True)
    landbot_user_id = Column(String, nullable=True, index=True, unique=True)
    status = Column(String, nullable=True, default="lead")
    age = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    goal = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    plans = relationship(
        "Plan",
        back_populates="client",
        foreign_keys="Plan.client_id",
        cascade="all, delete-orphan",
    )
    plan_versions = relationship(
        "PlanVersion",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    decision_logs = relationship(
        "DecisionLog",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    onboarding = relationship(
        "Onboarding",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    diets = relationship(
        "Diet",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    diet_versions = relationship(
        "DietVersion",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    checkins = relationship(
        "Checkin",
        back_populates="client",
        cascade="all, delete-orphan",
    )
