from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Onboarding(Base):
    __tablename__ = "onboarding"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    main_goal = Column(String, nullable=False)
    training_level = Column(String, nullable=False)
    injuries = Column(String, nullable=False)
    routine = Column(String, nullable=False)
    current_eating = Column(String, nullable=False)
    difficulties = Column(String, nullable=False)
    motivation = Column(String, nullable=False)
    
    client = relationship(
        "Client",
        back_populates="onboarding",
    )