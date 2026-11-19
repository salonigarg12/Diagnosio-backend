import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./diagnosio.db")

connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Shared SQLAlchemy declarative base for all ORM models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """Yield a database session per request and ensure it is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
