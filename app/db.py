import time
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def init_db_with_retry():
    from app import models
    last = None
    for _ in range(30):
        try:
            Base.metadata.create_all(bind=engine)
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
