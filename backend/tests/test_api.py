"""API and loader tests against a temporary SQLite database (see conftest.py)."""

import pandas as pd
import pytest
from conftest import write_generator_csvs
from sqlalchemy import text

from app.load_data import load_frames, read_csvs
from gridguard.losses import DEFAULT_TECHNICAL_LOSS


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
