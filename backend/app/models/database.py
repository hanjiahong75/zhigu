from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import sqlalchemy, os

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/zhigu.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    if "analysis_cache" in insp.get_table_names():
        cols = [c["name"] for c in insp.get_columns("analysis_cache")]
        if "user_message" not in cols:
            with engine.connect() as conn:
                sql = "ALTER TABLE analysis_cache ADD COLUMN user_message TEXT DEFAULT ''"
                conn.execute(sqlalchemy.text(sql))
                conn.commit()
