from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite = a simple file-based database, perfect for starting out
# No separate database server needed — it's just a file: jalseva.db
DATABASE_URL = "sqlite:///./jalseva.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # needed for SQLite only
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# This function gives each API request its own DB connection
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()