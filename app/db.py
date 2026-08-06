import time
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def apply_additive_migrations():
    """Fügt neue optionale Spalten hinzu, ohne bestehende Daten zu verändern."""
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("sites")}

    if "monitor_selector" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE sites "
                    "ADD COLUMN monitor_selector TEXT NOT NULL DEFAULT ''"
                )
            )

def init_db_with_retry():
    from app import models
    last = None
    for _ in range(30):
        try:
            Base.metadata.create_all(bind=engine)
            apply_additive_migrations()
            return
        except Exception as exc:
            last = exc
            time.sleep(2)
    raise last

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
