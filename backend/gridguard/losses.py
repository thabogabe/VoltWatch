"""Step 3: energy losses per transformer per month.

    loss_pct            = (supplied - billed) / supplied
    unexplained_loss_pct = loss_pct - expected technical loss

Technical losses (cable and transformer heating) are normally 5-8%, so only the gap
above that is a sign of unbilled consumption such as illegal connections.

Inputs are DataFrames with the same columns as the database tables, so this works on
synthetic data straight from the generator or on data read from Postgres.
"""

from collections.abc import Mapping

import pandas as pd

# Midpoint of the normal 5-8% range for township LV networks.
DEFAULT_TECHNICAL_LOSS = 0.065

BALANCE_COLUMNS = [
    "transformer_id",
    "month",
    "days_with_readings",
    "days_in_month",
    "supplied_kwh",
    "billed_kwh",
    "loss_kwh",
    "loss_pct",
    "technical_loss_pct",
    "unexplained_loss_pct",
]


def monthly_supplied(readings: pd.DataFrame) -> pd.DataFrame:
    """Sum daily transformer readings into months.

    readings columns: transformer_id, reading_date, energy_kwh
    """
    df = readings.assign(
        month=pd.to_datetime(readings["reading_date"]).dt.to_period("M").dt.to_timestamp()
    )
    out = (
        df.groupby(["transformer_id", "month"], as_index=False)
        .agg(supplied_kwh=("energy_kwh", "sum"), days_with_readings=("energy_kwh", "size"))
    )
    out["supplied_kwh"] = out["supplied_kwh"].astype(float)
    out["days_in_month"] = out["month"].dt.days_in_month
    return out


def monthly_billed(billing: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    """Sum customer bills up to their transformer per month.

    billing columns:   customer_id, billing_month, kwh_billed
    customers columns: id, transformer_id
    """
    df = billing.merge(
        customers[["id", "transformer_id"]], left_on="customer_id", right_on="id", how="inner"
    )
    df["month"] = pd.to_datetime(df["billing_month"]).dt.to_period("M").dt.to_timestamp()
    out = df.groupby(["transformer_id", "month"], as_index=False).agg(
        billed_kwh=("kwh_billed", "sum")
    )
    out["billed_kwh"] = out["billed_kwh"].astype(float)
    return out


def monthly_balance(
    readings: pd.DataFrame,
    billing: pd.DataFrame,
    customers: pd.DataFrame,
    technical_loss: float | Mapping[str, float] = DEFAULT_TECHNICAL_LOSS,
) -> pd.DataFrame:
    """Supplied vs billed energy and loss percentages per transformer per month.

    technical_loss is either one fraction for every transformer or a mapping of
    transformer_id -> fraction (transformers missing from the mapping get the default).

    Only months with transformer readings are returned; a month with readings but no
    bills counts as 0 kWh billed. Months with missing reading days understate supply,
    so check days_with_readings against days_in_month before relying on them.
    unexplained_loss_pct can be negative (billed more than expected), which usually
    points to a data problem rather than theft; it is left unclipped so that shows up.
    """
    balance = monthly_supplied(readings).merge(
        monthly_billed(billing, customers), on=["transformer_id", "month"], how="left"
    )
    balance["billed_kwh"] = balance["billed_kwh"].fillna(0.0)
    balance["loss_kwh"] = balance["supplied_kwh"] - balance["billed_kwh"]

    supplied = balance["supplied_kwh"].where(balance["supplied_kwh"] > 0)
    balance["loss_pct"] = balance["loss_kwh"] / supplied

    if isinstance(technical_loss, Mapping):
        balance["technical_loss_pct"] = (
            balance["transformer_id"].map(technical_loss).fillna(DEFAULT_TECHNICAL_LOSS)
        )
    else:
        balance["technical_loss_pct"] = float(technical_loss)
    balance["unexplained_loss_pct"] = balance["loss_pct"] - balance["technical_loss_pct"]

    return (
        balance[BALANCE_COLUMNS]
        .sort_values(["transformer_id", "month"])
        .reset_index(drop=True)
    )


def load_monthly_balance(
    engine, technical_loss: float | Mapping[str, float] = DEFAULT_TECHNICAL_LOSS
) -> pd.DataFrame:
    """Read the tables from the database and compute monthly_balance."""
    readings = pd.read_sql(
        "SELECT transformer_id, reading_date, energy_kwh FROM transformer_readings", engine
    )
    billing = pd.read_sql("SELECT customer_id, billing_month, kwh_billed FROM billing", engine)
    customers = pd.read_sql("SELECT id, transformer_id FROM customers", engine)
    return monthly_balance(readings, billing, customers, technical_loss)
