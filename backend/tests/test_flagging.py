import numpy as np
import pandas as pd

from gridguard.flagging import FlagConfig, evaluate_flags, flag_transformers

MONTHS = pd.period_range("2025-01", "2025-12", freq="M").to_timestamp()


def _transformers(n=30):
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "transformer_id": range(n),
            "lat": -26.25 + rng.uniform(-0.01, 0.01, n),
            "lon": 27.85 + rng.uniform(-0.01, 0.01, n),
        }
    )


def _losses(n=30, overrides=None, drop=None):
    """Normal transformers sit near 1% gap; `overrides` = {id: {month_index: gap}}."""
    rng = np.random.default_rng(1)
    rows = []
    for tid in range(n):
        for i, m in enumerate(MONTHS):
            gap = rng.normal(0.01, 0.005)
            gap = (overrides or {}).get(tid, {}).get(i, gap)
            if (tid, i) in (drop or set()):
                continue
            rows.append({"transformer_id": tid, "month": m, "unexplained_gap": gap})
    return pd.DataFrame(rows)


def test_three_consecutive_months_is_flagged():
    overrides = {0: {i: 0.12 for i in range(6, 12)}}  # six bad months in a row
    flags = flag_transformers(_losses(overrides=overrides), _transformers())
    row = flags.set_index("transformer_id").loc[0]
    assert row["persistent_flag"]
    assert row["longest_streak"] == 6
    assert row["current_streak"] == 6


def test_single_bad_month_is_not_persistent():
    overrides = {1: {5: 0.30}}  # one terrible billing cycle
    flags = flag_transformers(_losses(overrides=overrides), _transformers())
    assert not flags.set_index("transformer_id").loc[1, "persistent_flag"]


def test_two_months_is_not_enough():
    overrides = {2: {4: 0.10, 5: 0.10}}
    flags = flag_transformers(_losses(overrides=overrides), _transformers())
    assert not flags.set_index("transformer_id").loc[2, "persistent_flag"]


def test_missing_month_breaks_the_streak():
    # bad in Mar, Apr, (May missing), Jun, Jul -> longest real run is 2
    overrides = {3: {i: 0.10 for i in (2, 3, 5, 6)}}
    flags = flag_transformers(
        _losses(overrides=overrides, drop={(3, 4)}), _transformers()
    )
    row = flags.set_index("transformer_id").loc[3]
    assert row["longest_streak"] == 2
    assert not row["persistent_flag"]


def test_require_current_ignores_old_runs():
    overrides = {4: {i: 0.12 for i in range(0, 5)}}  # bad Jan-May, fine afterwards
    cfg = FlagConfig(require_current=True)
    flags = flag_transformers(_losses(overrides=overrides), _transformers(), cfg)
    row = flags.set_index("transformer_id").loc[4]
    assert row["longest_streak"] == 5
    assert not row["persistent_flag"]


def test_isolation_forest_catches_a_clear_outlier():
    # transformer 5 has a steadily growing gap that never crosses a high threshold,
    # so only the anomaly model can pick it up
    overrides = {5: {i: 0.01 + 0.004 * i for i in range(12)}}
    cfg = FlagConfig(gap_threshold=0.5, contamination=0.1)
    flags = flag_transformers(_losses(overrides=overrides), _transformers(), cfg)
    row = flags.set_index("transformer_id").loc[5]
    assert not row["persistent_flag"]
    assert row["anomaly_flag"]
    assert row["flag_reason"] == "anomaly"


def test_evaluate_flags():
    flags = pd.DataFrame(
        {"transformer_id": [1, 2, 3, 4], "flagged": [True, True, False, False]}
    )
    result = evaluate_flags(flags, true_ids=[1, 3])
    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5


def test_bad_input_columns_raise():
    bad = pd.DataFrame({"transformer_id": [1], "month": ["2025-01-01"]})
    try:
        flag_transformers(bad, _transformers())
    except ValueError as e:
        assert "unexplained_gap" in str(e)
    else:
        raise AssertionError("expected ValueError")
