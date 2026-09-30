"""Create the database tables.

Usage (from backend/):
    python -m app.create_tables           # create missing tables
    python -m app.create_tables --reset   # drop and recreate (deletes all data)
"""

import argparse

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import settings
from app.models import Base


def prepare_database(engine: Engine) -> None:
    """Create the DB_SCHEMA schema if one is set, and enable PostGIS.

    With DB_SCHEMA set, PostGIS is installed into that schema too (it is the first
    schema on the search path), so nothing is added to the shared "public" schema.
    """
    with engine.begin() as conn:
        if settings.db_schema:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.db_schema}"'))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="drop all tables first")
    args = parser.parse_args()

    from app.db import engine

    prepare_database(engine)
    if args.reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("Tables ready:", ", ".join(Base.metadata.tables))


if __name__ == "__main__":
    main()
