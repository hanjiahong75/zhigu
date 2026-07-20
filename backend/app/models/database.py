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
    # Migrate portfolio_items: add fund-specific columns
    if "portfolio_items" in insp.get_table_names():
        pi_cols = [c["name"] for c in insp.get_columns("portfolio_items")]
        fund_fields = {
            "holding_amount": "FLOAT DEFAULT 0",
            "cost_amount": "FLOAT DEFAULT 0",
            "holding_return": "FLOAT DEFAULT 0",
            "daily_return": "FLOAT DEFAULT 0",
            "daily_return_pct": "FLOAT DEFAULT 0",
            "sector": "VARCHAR(50) DEFAULT ''",
        }
        with engine.connect() as conn:
            for field, typedef in fund_fields.items():
                if field not in pi_cols:
                    sql = f"ALTER TABLE portfolio_items ADD COLUMN {field} {typedef}"
                    conn.execute(sqlalchemy.text(sql))
            conn.commit()
