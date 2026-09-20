import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# ---------------------------------------------------------------------------
# Load environment variables from .env
# ---------------------------------------------------------------------------

load_dotenv()


# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
#
# PostgreSQL is the active SiteAegis database when DATABASE_URL is present.
#
# SQLite remains as a fallback for environments where DATABASE_URL is not
# configured. The existing siteaegis.db file is NOT modified or deleted.
#

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./siteaegis.db",
)


# ---------------------------------------------------------------------------
# SQLAlchemy connection arguments
# ---------------------------------------------------------------------------

connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
    }


# ---------------------------------------------------------------------------
# SQLAlchemy engine
# ---------------------------------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

Base = declarative_base()


# ---------------------------------------------------------------------------
# FastAPI database dependency
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()