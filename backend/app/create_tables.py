"""Create the database tables.

Usage (from backend/):
    python -m app.create_tables           # create missing tables
    python -m app.create_tables --reset   # drop and recreate (deletes all data)
"""

import argparse

from sqlalchemy import text

from app.db import engine
from app.models import Base


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="drop all tables first")
    args = parser.parse_args()

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

    if args.reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("Tables ready:", ", ".join(Base.metadata.tables))


if __name__ == "__main__":
    main()
