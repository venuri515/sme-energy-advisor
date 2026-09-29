"""Run once to create all tables in the database."""
from app.models.database import engine, Base
from app.models import models  # noqa: F401

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Tables created.")