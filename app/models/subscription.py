from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="lead", index=True)
    plan_type = Column(String, nullable=True)
    payment_status = Column(String, nullable=False, default="pending")
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    last_payment_date = Column(Date, nullable=True)
    next_payment_date = Column(Date, nullable=True)
    manual_payment_method = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    client = relationship("Client", backref="subscription", uselist=False)

    __table_args__ = (
        Index("ix_subscription_client_status", "client_id", "status"),
        Index("ix_subscription_end_date", "end_date"),
    )
