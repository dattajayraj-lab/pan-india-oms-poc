"""Database engine and session factory.

SQLite is used for the POC (development plan §3.1). All access goes through the
SQLAlchemy ORM so the same models can target PostgreSQL Enterprise in production
(TS Cl. 2.9). SQLite-specific PRAGMAs are applied only when the URL is sqlite.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


def _apply_sqlite_pragmas(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL")
    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute("PRAGMA synchronous = NORMAL")
    cur.execute("PRAGMA busy_timeout = 5000")
    cur.close()


def make_engine(url: str) -> Engine:
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    eng = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        event.listen(eng, "connect", _apply_sqlite_pragmas)
    return eng


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine(get_settings().database_url)
        SessionLocal.configure(bind=_engine)
    return _engine


def set_engine(engine: Engine) -> None:
    """Used by tests to point the app at an isolated database."""
    global _engine
    _engine = engine
    SessionLocal.configure(bind=engine)


def get_db() -> Iterator[Session]:
    get_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
