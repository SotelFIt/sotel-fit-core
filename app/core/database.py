from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from os import getenv

DATABASE_URL = getenv("DATABASE_URL", "sqlite:///./test.db")

is_sqlite = "sqlite" in DATABASE_URL

_engine_kwargs: dict = {
    "connect_args": {"check_same_thread": False} if is_sqlite else {},
}
if not is_sqlite:
    _engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    })

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base = declarative_base()