from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Local-first SQLite database configuration
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "axiom.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Safe for SQLite multithreaded runs
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency injector for request database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
