import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Uses PostgreSQL if DATABASE_URL is set in environment, else falls back to local SQLite for tests/offline run
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "sqlite:///./eve_healthcare.db"
)

# SQLite requires 'check_same_thread', PostgreSQL does not
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()