"""
Database engine and session management.

This is the ONLY place that knows how to create a SQLAlchemy engine/session.
Everything else (repositories, services) receives a Session via dependency
injection (see `get_db`) - nothing outside this module talks to the engine
directly.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# SQLite needs this connect arg when used from multiple threads (as FastAPI /
# test clients do). It is a no-op for other engines (e.g. PostgreSQL).
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def get_db() -> Generator:
    """
    FastAPI dependency that yields a request-scoped DB session.

    Centralized DB error logging lives here rather than in each repository
    method: any SQLAlchemy error raised while a repository/service uses this
    session (e.g. during a query or commit) is thrown back into this
    generator at the `yield` point, so one try/except here covers the whole
    repository layer without scattering logging calls through it. Only the
    exception type is logged - never the query, parameters, or the
    connection URL (which can carry credentials).
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as exc:
        logger.error("database error exception_type=%s", type(exc).__name__)
        raise
    finally:
        db.close()
