from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gridguard.losses import monthly_balance

from . import db
from .db import get_session
from .models import Billing, Customer, Transformer, TransformerReading

app = FastAPI(title="VoltWatch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"


def load_by_transformer(filename: str) -> dict[str, dict]:
    """Read a pipeline output CSV (step 5/6) into {transformer_id: row}, NaN -> None."""
    csv_path = DATA_DIR / filename
    if not csv_path.exists():
        return {}
    df = pd.read_csv(csv_path)
    df = df.astype(object).where(pd.notna(df), None)
    return df.set_index("transformer_id").to_dict("index")


def load_risk_data() -> dict[str, dict]:
    """Step 6 output: risk_level, risk_score, loss_score, overload_score, driver, ..."""
    return load_by_transformer("risk.csv")


def load_forecast_data() -> dict[str, dict]:
    """Step 5 output: predicted_peak_kva, utilization_pct, at_risk."""
    return load_by_transformer("forecast_results.csv")


def transformer_summary(t, r: dict) -> dict:
    return {
        "id": t.id,
        "lat": float(t.lat),
        "lon": float(t.lon),
        "capacity_kva": float(t.capacity_kva),
        "ward": t.ward,
        "risk_level": r.get("risk_level") or "green",
        "risk_score": r.get("risk_score") or 0.0,
        "loss_score": r.get("loss_score") or 0.0,
        "overload_score": r.get("overload_score") or 0.0,
        "utilization_pct": r.get("utilization_pct"),
        "driver": r.get("driver") or "none",
    }


# Explicit columns (no PostGIS geom) so the queries also run on SQLite in tests.
TRANSFORMER_COLUMNS = (
    Transformer.id,
    Transformer.lat,
    Transformer.lon,
    Transformer.capacity_kva,
    Transformer.ward,
)


def monthly_history(db_session: Session, transformer_id: str) -> list[dict]:
    """Supplied vs billed per month (step 3) plus the monthly peak load, oldest first."""
    conn = db_session.connection()
    readings = pd.read_sql(
        select(
            TransformerReading.transformer_id,
            TransformerReading.reading_date,
            TransformerReading.energy_kwh,
            TransformerReading.peak_kva,
        ).where(TransformerReading.transformer_id == transformer_id),
        conn,
    )
    if readings.empty:
        return []
    billing = pd.read_sql(
        select(Billing.customer_id, Billing.billing_month, Billing.kwh_billed)
        .join(Customer, Customer.id == Billing.customer_id)
        .where(Customer.transformer_id == transformer_id),
        conn,
    )
    customers = pd.read_sql(
        select(Customer.id, Customer.transformer_id).where(
            Customer.transformer_id == transformer_id
        ),
        conn,
    )

    readings["energy_kwh"] = readings["energy_kwh"].astype(float)
    readings["peak_kva"] = pd.to_numeric(readings["peak_kva"], errors="coerce")
    billing["kwh_billed"] = billing["kwh_billed"].astype(float)

    balance = monthly_balance(readings, billing, customers)
    peaks = (
        readings.assign(
            month=pd.to_datetime(readings["reading_date"]).dt.to_period("M").dt.to_timestamp()
        )
        .groupby("month")["peak_kva"]
        .max()
    )
    balance["peak_kva"] = balance["month"].map(peaks)

    def num(value, digits):
        return None if pd.isna(value) else round(float(value), digits)

    return [
        {
            "month": row.month.date().isoformat(),
            "supplied_kwh": num(row.supplied_kwh, 2),
            "billed_kwh": num(row.billed_kwh, 2),
            # Fraction net of technical loss; negative means billed more than expected.
            "unexplained_loss_pct": num(row.unexplained_loss_pct, 4),
            "peak_kva": num(row.peak_kva, 2),
        }
        for row in balance.itertuples()
    ]


@app.get("/health")
def health_check():
    schema = db.current_schema()
    return {
        "status": "ok",
        "message": "GridGuard API is running",
        "database": "down" if schema is None else "up",
        "schema": schema,
    }


@app.get("/transformers")
def get_transformers(db_session: Session = Depends(get_session)):
    """Returns all transformers with real risk scores for the frontend map."""
    risk = load_risk_data()
    rows = db_session.execute(select(*TRANSFORMER_COLUMNS).order_by(Transformer.id)).all()
    return [transformer_summary(t, risk.get(t.id, {})) for t in rows]


@app.get("/transformers/{transformer_id}")
def get_transformer(transformer_id: str, db_session: Session = Depends(get_session)):
    """Returns detailed stats, history, and forecast for a single transformer."""
    t = db_session.execute(
        select(*TRANSFORMER_COLUMNS).where(Transformer.id == transformer_id)
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transformer not found")

    customer_count, indigent_count = db_session.execute(
        select(
            func.count(Customer.id),
            func.count(Customer.id).filter(Customer.is_indigent.is_(True)),
        ).where(Customer.transformer_id == transformer_id)
    ).one()

    history = monthly_history(db_session, transformer_id)
    f = load_forecast_data().get(transformer_id)

    forecast = None
    if f is not None:
        next_month = None
        if history:
            next_month = (pd.Timestamp(history[-1]["month"]) + pd.DateOffset(months=1)).date()
        forecast = {
            "month": next_month.isoformat() if next_month else None,
            "predicted_peak_kva": f.get("predicted_peak_kva"),
            "utilization_pct": f.get("utilization_pct"),
            "at_risk": bool(f.get("at_risk")),
        }

    return {
        **transformer_summary(t, load_risk_data().get(transformer_id, {})),
        "customer_count": customer_count,
        "indigent_count": indigent_count,
        "history": history,
        "forecast": forecast,
    }


@app.get("/summary")
def get_summary(db_session: Session = Depends(get_session)):
    """Returns headline metrics and dynamic risk counts for the dashboard banner."""
    risk = load_risk_data()
    levels = [r.get("risk_level") for r in risk.values()]
    return {
        "total_transformers": db_session.scalar(select(func.count(Transformer.id))),
        "total_customers": db_session.scalar(select(func.count(Customer.id))),
        "risk_counts": {level: levels.count(level) for level in ("green", "amber", "red")},
    }
