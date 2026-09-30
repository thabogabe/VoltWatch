"""Step 4 - flag persistent gaps and unusual transformers.

Input (produced by step 3, one row per transformer per month):
    losses:       transformer_id, month, unexplained_gap
                  (unexplained_gap is a fraction: 0.06 = 6 percentage points of
                   supplied energy that is neither billed nor explained by
                   normal technical losses)
    transformers: transformer_id, lat, lon   (extra columns are ignored)

Output: one row per transformer with two independent signals and a combined flag.

    1. Persistent gap  - unexplained_gap above a threshold for N or more
                         CONSECUTIVE calendar months (a missing month breaks the run).
    2. Anomaly         - Isolation Forest on per-transformer features, including how
                         the transformer compares with its nearest geographic neighbours.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import BallTree

REQUIRED_LOSS_COLS = {"transformer_id", "month", "unexplained_gap"}
REQUIRED_TX_COLS = {"transformer_id", "lat", "lon"}

FEATURE_COLS = [
    "mean_gap",
    "max_gap",
    "std_gap",
    "gap_trend",
    "longest_streak",
    "neighbour_gap_diff",
]


@dataclass(frozen=True)
class FlagConfig:
    gap_threshold: float = 0.04  # unexplained gap that counts as "bad" for a month
    min_consecutive_months: int = 3  # months in a row before we flag
    require_current: bool = False  # True = the run must still be going in the latest month
    n_neighbours: int = 8  # neighbours used for the "unusual vs neighbours" feature
    contamination: float = 0.10  # expected share of anomalous transformers
    n_estimators: int = 200
    random_state: int = 42


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _check_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{name} is missing columns: {sorted(missing)}")


def _monthly_matrix(losses: pd.DataFrame) -> pd.DataFrame:
    """Wide table: one row per transformer, one column per calendar month.

    Months with no data stay NaN so they break a streak instead of being skipped.
    """
    df = losses[["transformer_id", "month", "unexplained_gap"]].copy()
    df["month"] = pd.to_datetime(df["month"]).dt.to_period("M")
    wide = df.pivot_table(
        index="transformer_id",
        columns="month",
        values="unexplained_gap",
        aggfunc="mean",
    )
    full_range = pd.period_range(wide.columns.min(), wide.columns.max(), freq="M")
    return wide.reindex(columns=full_range)


def _streaks(above: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Longest and current run of True values along each row."""
    n_rows, n_cols = above.shape
    run = np.zeros(n_rows, dtype=int)
    longest = np.zeros(n_rows, dtype=int)
    for j in range(n_cols):
        run = np.where(above[:, j], run + 1, 0)
        longest = np.maximum(longest, run)
    return longest, run


def _trend(values: np.ndarray) -> float:
    """Slope of the gap over time (change per month). 0 if fewer than 2 points."""
    mask = ~np.isnan(values)
    if mask.sum() < 2:
        return 0.0
    x = np.arange(len(values))[mask]
    return float(np.polyfit(x, values[mask], 1)[0])


def _neighbour_mean(tx: pd.DataFrame, values: np.ndarray, k: int) -> np.ndarray:
    """Mean of `values` over each transformer's k nearest neighbours (haversine)."""
    n = len(tx)
    if n < 2:
        return np.zeros(n)
    k = min(k, n - 1)
    coords = np.radians(tx[["lat", "lon"]].to_numpy(dtype=float))
    tree = BallTree(coords, metric="haversine")
    _, idx = tree.query(coords, k=k + 1)
    # drop the transformer itself (robust even if two share identical coordinates)
    neighbours = np.array([row[row != i][:k] for i, row in enumerate(idx)])
    return values[neighbours].mean(axis=1)


# --------------------------------------------------------------------------- #
# main entry point
# --------------------------------------------------------------------------- #
def flag_transformers(
    losses: pd.DataFrame,
    transformers: pd.DataFrame,
    config: FlagConfig | None = None,
) -> pd.DataFrame:
    """Return one row per transformer with persistence, anomaly and combined flags."""
    cfg = config or FlagConfig()
    _check_columns(losses, REQUIRED_LOSS_COLS, "losses")
    _check_columns(transformers, REQUIRED_TX_COLS, "transformers")

    wide = _monthly_matrix(losses)
    values = wide.to_numpy(dtype=float)

    # ---- signal 1: persistent gap ------------------------------------------
    above = np.greater(values, cfg.gap_threshold)  # NaN -> False
    longest, current = _streaks(above)

    feats = pd.DataFrame(index=wide.index)
    feats["months_observed"] = np.sum(~np.isnan(values), axis=1)
    feats["mean_gap"] = np.nanmean(values, axis=1)
    feats["max_gap"] = np.nanmax(values, axis=1)
    feats["std_gap"] = np.nan_to_num(np.nanstd(values, axis=1))
    feats["gap_trend"] = [_trend(row) for row in values]
    feats["longest_streak"] = longest
    feats["current_streak"] = current

    streak_for_rule = feats["current_streak"] if cfg.require_current else feats["longest_streak"]
    feats["persistent_flag"] = streak_for_rule >= cfg.min_consecutive_months

    # ---- signal 2: Isolation Forest, compared with neighbours ---------------
    tx = (
        transformers.drop_duplicates("transformer_id")
        .set_index("transformer_id")
        .reindex(feats.index)
    )
    if tx[["lat", "lon"]].isna().any().any():
        raise ValueError("Some transformers with loss data have no lat/lon.")

    feats["neighbour_gap_diff"] = feats["mean_gap"].to_numpy() - _neighbour_mean(
        tx, feats["mean_gap"].to_numpy(), cfg.n_neighbours
    )

    X = feats[FEATURE_COLS].to_numpy(dtype=float)
    if len(feats) >= 2:
        forest = IsolationForest(
            n_estimators=cfg.n_estimators,
            contamination=cfg.contamination,
            random_state=cfg.random_state,
        )
        is_outlier = forest.fit_predict(X) == -1
        raw = -forest.score_samples(X)  # higher = more unusual
        span = raw.max() - raw.min()
        score = (raw - raw.min()) / span if span > 0 else np.zeros_like(raw)
    else:
        is_outlier = np.zeros(len(feats), dtype=bool)
        score = np.zeros(len(feats))

    feats["anomaly_score"] = score
    feats["anomaly_flag"] = is_outlier

    # ---- combine ------------------------------------------------------------
    feats["flagged"] = feats["persistent_flag"] | feats["anomaly_flag"]
    feats["flag_reason"] = np.select(
        [
            feats["persistent_flag"] & feats["anomaly_flag"],
            feats["persistent_flag"],
            feats["anomaly_flag"],
        ],
        ["persistent+anomaly", "persistent", "anomaly"],
        default="none",
    )

    cols = [
        "months_observed",
        "mean_gap",
        "max_gap",
        "longest_streak",
        "current_streak",
        "neighbour_gap_diff",
        "persistent_flag",
        "anomaly_score",
        "anomaly_flag",
        "flagged",
        "flag_reason",
    ]
    return feats[cols].reset_index()


# --------------------------------------------------------------------------- #
# tuning against the synthetic ground truth (step 2)
# --------------------------------------------------------------------------- #
def evaluate_flags(flags: pd.DataFrame, true_ids, column: str = "flagged") -> dict:
    """Precision / recall of a flag column against the injected illegal-load ids."""
    truth = flags["transformer_id"].isin(set(true_ids))
    pred = flags[column].astype(bool)
    tp = int((truth & pred).sum())
    fp = int((~truth & pred).sum())
    fn = int((truth & ~pred).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "column": column,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
    }
