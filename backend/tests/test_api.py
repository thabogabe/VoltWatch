"""API and loader tests against a temporary SQLite database (no Postgres needed)."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import main
from app.db import get_session
from app.load_data import load_frames, read_csvs
from gridguard.losses import DEFAULT_TECHNICAL_LOSS

# Same tables as app/models.py minus the PostGIS geom column, which SQLite lacks.
SQLITE_DDL = [
    """CREATE TABLE transformers (id TEXT PRIMARY KEY, name TEXT, ward TEXT,
        lat NUMERIC NOT NULL, lon NUMERIC NOT NULL, capacity_kva NUMERIC NOT NULL)""",
    """CREATE TABLE customers (id TEXT PRIMARY KEY, transformer_id TEXT NOT NULL,
        is_indigent BOOLEAN NOT NULL, meter_type TEXT NOT NULL)""",
    """CREATE TABLE transformer_readings (transformer_id TEXT, reading_date DATE,
        energy_kwh NUMERIC NOT NULL, peak_kva NUMERIC, temperature_c NUMERIC,
        PRIMARY KEY (transformer_id, reading_date))""",
    """CREATE TABLE billing (customer_id TEXT, billing_month DATE,
        kwh_billed NUMERIC NOT NULL, PRIMARY KEY (customer_id, billing_month))""",
]


def write_generator_csvs(folder):
    """Step 2-style CSVs: T1 has June + July readings, T2 only June."""
    pd.DataFrame(
        {"id": ["T1", "T2"], "lat": [-26.25, -26.26], "lon": [27.85, 27.86], "capacity_kva": [100, 200]}
    ).to_csv(folder / "transformers.csv", index=False)
    pd.DataFrame(
        {"id": ["C1", "C2", "C3"], "transformer_id": ["T1", "T1", "T2"], "is_indigent": [True, False, False]}
    ).to_csv(folder / "customers.csv", index=False)  # no meter_type column
    days = [d.date() for d in pd.date_range("2026-06-01", "2026-07-31")]
    june = [d for d in days if d.month == 6]
    readings = pd.concat(
        [
            pd.DataFrame({"transformer_id": "T1", "reading_date": days, "energy_kwh": 100.0,
                          "peak_kva": [50.0 if d.month == 6 else 60.0 for d in days], "temperature_c": 12.0}),
            pd.DataFrame({"transformer_id": "T2", "reading_date": june, "energy_kwh": 50.0,
                          "peak_kva": 20.0, "temperature_c": 12.0}),
        ]
    )
    readings.to_csv(folder / "transformer_readings.csv", index=False)
    pd.DataFrame(
        {
            "customer_id": ["C1", "C2", "C3"],
            "billing_month": ["2026-06-01", "2026-06-01", "2026-06-01"],
            "kwh_billed": [1500.0, 900.0, 1400.0],  # T1 June: 3000 supplied, 2400 billed
        }
    ).to_csv(folder / "billing.csv", index=False)


def write_pipeline_outputs(folder):
    pd.DataFrame(
        {
            "transformer_id": ["T1", "T2"],
            "loss_score": [1.0, 0.0],
            "utilization_pct": [80.0, None],  # T2 has no forecast -> NaN in the CSV
            "overload_score": [0.47, 0.0],
            "risk_score": [1.0, 0.0],
            "risk_level": ["red", "green"],
            "driver": ["both", "none"],
        }
    ).to_csv(folder / "risk.csv", index=False)
    pd.DataFrame(
        {"transformer_id": ["T1"], "capacity_kva": [100], "predicted_peak_kva": [80.0],
         "utilization_pct": [80.0], "at_risk": [False]}
    ).to_csv(folder / "forecast_results.csv", index=False)


@pytest.fixture
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with eng.begin() as conn:
        for ddl in SQLITE_DDL:
            conn.execute(text(ddl))
    write_generator_csvs(tmp_path)
    load_frames(eng, read_csvs(tmp_path))
    return eng


@pytest.fixture
def client(engine, tmp_path, monkeypatch):
    write_pipeline_outputs(tmp_path)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    Session = sessionmaker(bind=engine)

    def session_override():
        with Session() as session:
            yield session

    main.app.dependency_overrides[get_session] = session_override
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


# --- loader -----------------------------------------------------------------


def test_loader_fills_defaults_and_counts_rows(engine):
    with engine.connect() as conn:
        counts = {
            t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            for t in ["transformers", "customers", "transformer_readings", "billing"]
        }
        meter_types = conn.execute(text("SELECT DISTINCT meter_type FROM customers")).scalars().all()
    assert counts == {"transformers": 2, "customers": 3, "transformer_readings": 61 + 30, "billing": 3}
    assert meter_types == ["prepaid"]


def test_loader_replaces_rows_instead_of_duplicating(engine, tmp_path):
    load_frames(engine, read_csvs(tmp_path))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM customers")).scalar() == 3


def test_loader_accepts_old_transformer_id_column(tmp_path):
    write_generator_csvs(tmp_path)
    tx = pd.read_csv(tmp_path / "transformers.csv").rename(columns={"id": "transformer_id"})
    tx.to_csv(tmp_path / "transformers.csv", index=False)
    assert list(read_csvs(tmp_path)["transformers"]["id"]) == ["T1", "T2"]


# --- API --------------------------------------------------------------------


def test_transformers_list_uses_risk_output(client):
    body = client.get("/transformers").json()
    by_id = {t["id"]: t for t in body}
    assert set(by_id) == {"T1", "T2"}
    assert by_id["T1"]["risk_level"] == "red"
    assert by_id["T1"]["driver"] == "both"
    assert by_id["T1"]["capacity_kva"] == 100
    assert by_id["T2"]["utilization_pct"] is None  # NaN in the CSV becomes null


def test_transformer_detail_history_matches_step_3(client):
    body = client.get("/transformers/T1").json()
    june, july = body["history"]
    assert june["month"] == "2026-06-01"
    assert june["supplied_kwh"] == 3000
    assert june["billed_kwh"] == 2400
    assert june["unexplained_loss_pct"] == pytest.approx(0.20 - DEFAULT_TECHNICAL_LOSS, abs=1e-4)
    assert june["peak_kva"] == 50
    assert july["billed_kwh"] == 0  # no bills yet -> full month unexplained
    assert july["peak_kva"] == 60
    assert body["customer_count"] == 2
    assert body["indigent_count"] == 1


def test_transformer_detail_forecast_from_step_5(client):
    forecast = client.get("/transformers/T1").json()["forecast"]
    assert forecast == {
        "month": "2026-08-01",  # month after the last history month
        "predicted_peak_kva": 80.0,
        "utilization_pct": 80.0,
        "at_risk": False,
    }


def test_transformer_without_forecast(client):
    body = client.get("/transformers/T2").json()
    assert body["forecast"] is None
    assert len(body["history"]) == 1


def test_unknown_transformer_is_404(client):
    assert client.get("/transformers/NOPE").status_code == 404


def test_summary_counts(client):
    assert client.get("/summary").json() == {
        "total_transformers": 2,
        "total_customers": 3,
        "risk_counts": {"green": 1, "amber": 0, "red": 1},
    }


def test_missing_pipeline_outputs_default_to_green(client, tmp_path):
    (tmp_path / "risk.csv").unlink()
    body = client.get("/transformers").json()
    assert {t["risk_level"] for t in body} == {"green"}
