"""Load the synthetic CSVs (step 2 output in data/) into the database.

Usage (from backend/, with the database running and DATABASE_URL set in .env):
    python -m app.load_data                 # create tables if needed, replace all rows
    python -m app.load_data --data ../data  # read the CSVs from another folder

The analysis outputs (data/risk.csv, data/forecast_results.csv) are not loaded;
the API reads them from data/ directly.
"""

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.models import Base

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# table -> (csv file, columns to load, defaults for columns the CSV may not have)
TABLES = {
    "transformers": (
        "transformers.csv",
        ["id", "name", "ward", "lat", "lon", "capacity_kva"],
        {"name": None, "ward": None},
    ),
    "customers": (
        "customers.csv",
        ["id", "transformer_id", "is_indigent", "meter_type"],
        {"is_indigent": False, "meter_type": "prepaid"},
    ),
    "transformer_readings": (
        "transformer_readings.csv",
        ["transformer_id", "reading_date", "energy_kwh", "peak_kva", "temperature_c"],
        {"peak_kva": None, "temperature_c": None},
    ),
    "billing": (
        "billing.csv",
        ["customer_id", "billing_month", "kwh_billed"],
        {},
    ),
}
DATE_COLUMNS = {"reading_date", "billing_month"}

# Parents before children when inserting, the reverse when deleting.
LOAD_ORDER = ["transformers", "customers", "transformer_readings", "billing"]


def read_csvs(data_dir: Path) -> dict[str, pd.DataFrame]:
    frames = {}
    for table, (filename, columns, defaults) in TABLES.items():
        df = pd.read_csv(data_dir / filename)
        if table == "transformers" and "id" not in df.columns:
            df = df.rename(columns={"transformer_id": "id"})  # older generator output
        for column, value in defaults.items():
            if column not in df.columns:
                df[column] = value
        missing = set(columns) - set(df.columns)
        if missing:
            raise ValueError(f"{filename} is missing columns: {sorted(missing)}")
        df = df[columns].copy()
        for column in DATE_COLUMNS & set(columns):
            df[column] = pd.to_datetime(df[column]).dt.date
        frames[table] = df
    return frames


def load_frames(engine: Engine, frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Replace the contents of the four tables in one transaction."""
    with engine.begin() as conn:
        for table in reversed(LOAD_ORDER):
            conn.execute(text(f"DELETE FROM {table}"))
        for table in LOAD_ORDER:
            frames[table].to_sql(
                table, conn, if_exists="append", index=False, method="multi", chunksize=2000
            )
    return {table: len(frames[table]) for table in LOAD_ORDER}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_DIR, help="folder with the CSVs")
    args = parser.parse_args()

    # imported here so tests can use their own engine
    from app.create_tables import prepare_database
    from app.db import engine

    prepare_database(engine)
    Base.metadata.create_all(engine)

    counts = load_frames(engine, read_csvs(args.data))
    for table, n in counts.items():
        print(f"{table:22s} {n:>8,} rows")


if __name__ == "__main__":
    main()
