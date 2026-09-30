import pandas as pd
import pytest

from gridguard.losses import DEFAULT_TECHNICAL_LOSS, monthly_balance


def daily_readings(transformer_id: str, month: str, kwh_per_day: float, days: int | None = None):
    dates = pd.date_range(month, periods=days or pd.Period(month).days_in_month, freq="D")
    return pd.DataFrame(
        {"transformer_id": transformer_id, "reading_date": dates, "energy_kwh": kwh_per_day}
    )


@pytest.fixture
def customers():
    return pd.DataFrame(
        {"id": ["C1", "C2", "C3"], "transformer_id": ["T1", "T1", "T2"]}
    )


def test_loss_and_unexplained_gap(customers):
    # T1: 30 days x 100 kWh = 3000 supplied, 2400 billed -> 20% loss, 13.5% unexplained
    readings = daily_readings("T1", "2026-06-01", 100)
    billing = pd.DataFrame(
        {
            "customer_id": ["C1", "C2"],
            "billing_month": pd.to_datetime(["2026-06-01", "2026-06-01"]),
            "kwh_billed": [1500.0, 900.0],
        }
    )

    row = monthly_balance(readings, billing, customers).iloc[0]

    assert row["supplied_kwh"] == 3000
    assert row["billed_kwh"] == 2400
    assert row["loss_kwh"] == 600
    assert row["loss_pct"] == pytest.approx(0.20)
    assert row["unexplained_loss_pct"] == pytest.approx(0.20 - DEFAULT_TECHNICAL_LOSS)
    assert row["days_with_readings"] == row["days_in_month"] == 30


def test_normal_technical_loss_leaves_no_gap(customers):
    readings = daily_readings("T2", "2026-07-01", 100)  # 3100 supplied
    billing = pd.DataFrame(
        {
            "customer_id": ["C3"],
            "billing_month": pd.to_datetime(["2026-07-01"]),
            "kwh_billed": [3100 * (1 - DEFAULT_TECHNICAL_LOSS)],
        }
    )

    row = monthly_balance(readings, billing, customers).iloc[0]

    assert row["unexplained_loss_pct"] == pytest.approx(0.0)


def test_month_without_bills_counts_as_zero_billed(customers):
    readings = daily_readings("T1", "2026-06-01", 50)
    empty_billing = pd.DataFrame(columns=["customer_id", "billing_month", "kwh_billed"])

    row = monthly_balance(readings, empty_billing, customers).iloc[0]

    assert row["billed_kwh"] == 0
    assert row["loss_pct"] == pytest.approx(1.0)


def test_zero_supply_gives_no_loss_pct(customers):
    readings = daily_readings("T1", "2026-06-01", 0)
    billing = pd.DataFrame(
        {"customer_id": ["C1"], "billing_month": pd.to_datetime(["2026-06-01"]), "kwh_billed": [10.0]}
    )

    row = monthly_balance(readings, billing, customers).iloc[0]

    assert pd.isna(row["loss_pct"])
    assert pd.isna(row["unexplained_loss_pct"])


def test_partial_month_is_reported(customers):
    readings = daily_readings("T1", "2026-06-01", 100, days=20)
    empty_billing = pd.DataFrame(columns=["customer_id", "billing_month", "kwh_billed"])

    row = monthly_balance(readings, empty_billing, customers).iloc[0]

    assert row["days_with_readings"] == 20
    assert row["days_in_month"] == 30


def test_per_transformer_technical_loss(customers):
    readings = pd.concat(
        [daily_readings("T1", "2026-06-01", 100), daily_readings("T2", "2026-06-01", 100)]
    )
    billing = pd.DataFrame(
        {
            "customer_id": ["C1", "C3"],
            "billing_month": pd.to_datetime(["2026-06-01", "2026-06-01"]),
            "kwh_billed": [2700.0, 2700.0],  # 10% loss on both
        }
    )

    balance = monthly_balance(readings, billing, customers, technical_loss={"T1": 0.05})
    gaps = balance.set_index("transformer_id")["unexplained_loss_pct"]

    assert gaps["T1"] == pytest.approx(0.05)
    assert gaps["T2"] == pytest.approx(0.10 - DEFAULT_TECHNICAL_LOSS)


def test_months_are_separate_rows(customers):
    readings = pd.concat(
        [daily_readings("T1", "2026-06-01", 100), daily_readings("T1", "2026-07-01", 100)]
    )
    billing = pd.DataFrame(
        {
            "customer_id": ["C1", "C1"],
            "billing_month": pd.to_datetime(["2026-06-01", "2026-07-01"]),
            "kwh_billed": [3000.0, 1550.0],
        }
    )

    balance = monthly_balance(readings, billing, customers)

    assert list(balance["month"].dt.month) == [6, 7]
    assert balance["loss_pct"].tolist() == pytest.approx([0.0, 0.5])
