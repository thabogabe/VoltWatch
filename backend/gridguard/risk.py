"""Step 6: combine loss and overload into one risk score per transformer.

    loss_score      0-1  how big the unexplained gap is (step 4). A gap that is not
                         persistent or anomalous only counts half, so one bad billing
                         cycle can't turn a transformer red on its own.
    overload_score  0-1  how close the forecast is to capacity (step 5).
                         60% utilisation -> 0, 90% -> 0.75 (red), 100%+ -> 1.
    risk_score      0-1  1 - (1 - w_loss * loss) * (1 - w_overload * overload)

The combination means either problem alone can make a transformer red, and having
both raises the score further. A plain weighted average would cap an overloaded
transformer with no losses at amber, even at 110% of capacity.

Buckets: green < 0.4, amber 0.4-0.7, red >= 0.7.

Run from backend/:
    python -m gridguard.risk            # reads data/flags.csv + data/forecast_results.csv
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

REQUIRED_FLAG_COLS = {"transformer_id", "mean_gap", "persistent_flag", "anomaly_flag"}
REQUIRED_FORECAST_COLS = {"transformer_id", "utilization_pct"}


@dataclass(frozen=True)
class RiskConfig:
    gap_full: float = 0.20  # unexplained gap that counts as maximum loss risk
    unconfirmed_gap_weight: float = 0.5  # weight of a gap with no persistent/anomaly flag
    util_start: float = 60.0  # utilisation % where overload risk starts
    util_full: float = 100.0  # utilisation % where overload risk is maximum
    loss_weight: float = 1.0
    overload_weight: float = 1.0
    amber_at: float = 0.4
    red_at: float = 0.7


def _check_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{name} is missing columns: {sorted(missing)}")


def loss_score(flags: pd.DataFrame, cfg: RiskConfig) -> pd.Series:
    gap = np.clip(flags["mean_gap"].astype(float) / cfg.gap_full, 0.0, 1.0)
    confirmed = flags["persistent_flag"].astype(bool) | flags["anomaly_flag"].astype(bool)
    return gap.where(confirmed, gap * cfg.unconfirmed_gap_weight)


def overload_score(forecast: pd.DataFrame, cfg: RiskConfig) -> pd.Series:
    util = forecast["utilization_pct"].astype(float)
    return np.clip((util - cfg.util_start) / (cfg.util_full - cfg.util_start), 0.0, 1.0)


def risk_level(score: pd.Series, cfg: RiskConfig) -> pd.Series:
    return pd.Series(
        np.select([score >= cfg.red_at, score >= cfg.amber_at], ["red", "amber"], "green"),
        index=score.index,
    )


def score_transformers(
    flags: pd.DataFrame, forecast: pd.DataFrame, config: RiskConfig | None = None
) -> pd.DataFrame:
    """One row per transformer with loss, overload and combined risk.

    A transformer missing from one input gets 0 for that part, and has_loss_data /
    has_forecast show which inputs it had.
    """
    cfg = config or RiskConfig()
    _check_columns(flags, REQUIRED_FLAG_COLS, "flags")
    _check_columns(forecast, REQUIRED_FORECAST_COLS, "forecast")

    loss = flags[["transformer_id"]].assign(loss_score=loss_score(flags, cfg).to_numpy())
    over = forecast[["transformer_id", "utilization_pct"]].assign(
        overload_score=overload_score(forecast, cfg).to_numpy()
    )
    df = loss.merge(over, on="transformer_id", how="outer", indicator=True)
    df["has_loss_data"] = df["_merge"] != "right_only"
    df["has_forecast"] = df["_merge"] != "left_only"
    df[["loss_score", "overload_score"]] = df[["loss_score", "overload_score"]].fillna(0.0)

    weighted_loss = cfg.loss_weight * df["loss_score"]
    weighted_over = cfg.overload_weight * df["overload_score"]
    df["risk_score"] = 1 - (1 - weighted_loss) * (1 - weighted_over)
    df["risk_level"] = risk_level(df["risk_score"], cfg)

    # Which signal to act on: loss -> regularisation queue, overload -> upgrade/maintenance.
    loss_high = df["loss_score"] >= cfg.amber_at
    over_high = df["overload_score"] >= cfg.amber_at
    df["driver"] = np.select(
        [loss_high & over_high, loss_high, over_high], ["both", "loss", "overload"], "none"
    )

    cols = [
        "transformer_id",
        "loss_score",
        "utilization_pct",
        "overload_score",
        "risk_score",
        "risk_level",
        "driver",
        "has_loss_data",
        "has_forecast",
    ]
    return df[cols].sort_values("risk_score", ascending=False).reset_index(drop=True)


def evaluate_risk(risk: pd.DataFrame, true_ids) -> dict:
    """How the buckets line up with the injected illegal load (step 2 ground truth).

    illegal_caught: share of illegal-load transformers that are amber or red
    normal_red:     share of normal transformers that are red (false alarms)
    """
    truth = risk["transformer_id"].isin(set(true_ids))
    flagged = risk["risk_level"].isin(["amber", "red"])
    red = risk["risk_level"] == "red"
    return {
        "illegal_caught": round(float(flagged[truth].mean()), 3) if truth.any() else None,
        "illegal_red": round(float(red[truth].mean()), 3) if truth.any() else None,
        "normal_red": round(float(red[~truth].mean()), 3) if (~truth).any() else None,
        "counts": risk["risk_level"].value_counts().reindex(["green", "amber", "red"], fill_value=0).to_dict(),
    }


def main() -> None:
    flags = pd.read_csv(DATA_DIR / "flags.csv")
    forecast = pd.read_csv(DATA_DIR / "forecast_results.csv")
    risk = score_transformers(flags, forecast)

    out = DATA_DIR / "risk.csv"
    risk.to_csv(out, index=False)
    print(risk["risk_level"].value_counts().to_string())

    truth_file = DATA_DIR / "ground_truth.csv"
    if truth_file.exists():
        truth = pd.read_csv(truth_file)
        print(evaluate_risk(risk, truth.loc[truth["has_illegal_load"], "transformer_id"]))
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
