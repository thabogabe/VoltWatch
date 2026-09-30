from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},
)


def use_schema(target: Engine, schema: str) -> None:
    """Point every new connection at `schema` first, so tables and PostGIS live there."""

    @event.listens_for(target, "connect")
    def set_search_path(dbapi_connection, _record):
        # Autocommit so the SET isn't undone when the pool rolls back.
        previous = dbapi_connection.autocommit
        dbapi_connection.autocommit = True
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}", public')
        dbapi_connection.autocommit = previous


if settings.db_schema:
    use_schema(engine, settings.db_schema)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def ping() -> bool:
    return current_schema() is not None


def current_schema() -> str | None:
    """Schema that unqualified table names resolve to, or None if the DB is unreachable."""
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT current_schema()")).scalar() or ""
    except Exception:
        return None
