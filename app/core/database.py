from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from os import getenv

# Database URL
DATABASE_URL = getenv("DATABASE_URL", "sqlite:///./test.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Base (para modelos SQLAlchemy)
from sqlalchemy.orm import declarative_base
Base = declarative_base()
