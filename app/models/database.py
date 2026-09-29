"""SQLAlchemy setup: the engine, session, and base class every model inherits from."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://sme:change_me@localhost:5432/sme_energy",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: gives each request its own DB session, then closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()