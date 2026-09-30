import pandas as pd
import pytest

from gridguard.risk import RiskConfig, evaluate_risk, score_transformers


def flags(rows):
    return pd.DataFrame(
        rows, columns=["transformer_id", "mean_gap", "persistent_flag", "anomaly_flag"]
    )


def forecast(rows):
    return pd.DataFrame(rows, columns=["transformer_id", "utilization_pct"])


def score(flag_rows, forecast_rows, **cfg):
    risk = score_transformers(flags(flag_rows), forecast(forecast_rows), RiskConfig(**cfg))
    return risk.set_index("transformer_id")


def test_healthy_transformer_is_green():
    row = score([("T1", 0.01, False, False)], [("T1", 50.0)]).loc["T1"]
    assert row["risk_score"] == pytest.approx(0.0, abs=0.05)
    assert row["risk_level"] == "green"
    assert row["driver"] == "none"


def test_large_persistent_gap_is_red():
    row = score([("T1", 0.25, True, False)], [("T1", 50.0)]).loc["T1"]
    assert row["loss_score"] == 1.0
    assert row["risk_level"] == "red"
    assert row["driver"] == "loss"


def test_same_gap_without_flag_counts_half():
    risk = score(
        [("T1", 0.10, True, False), ("T2", 0.10, False, False)],
        [("T1", 0.0), ("T2", 0.0)],
    )
    assert risk.loc["T1", "loss_score"] == pytest.approx(0.5)
    assert risk.loc["T2", "loss_score"] == pytest.approx(0.25)


def test_negative_gap_scores_zero():
    row = score([("T1", -0.15, False, False)], [("T1", 0.0)]).loc["T1"]
    assert row["loss_score"] == 0.0


def test_forecast_above_90_percent_is_red_without_losses():
    row = score([("T1", 0.0, False, False)], [("T1", 92.0)]).loc["T1"]
    assert row["overload_score"] == pytest.approx(0.8)
    assert row["risk_level"] == "red"
    assert row["driver"] == "overload"


def test_two_moderate_problems_add_up():
    # each alone is amber (0.5), together 1 - 0.5 * 0.5 = 0.75 -> red
    row = score([("T1", 0.10, True, False)], [("T1", 80.0)]).loc["T1"]
    assert row["loss_score"] == pytest.approx(0.5)
    assert row["overload_score"] == pytest.approx(0.5)
    assert row["risk_score"] == pytest.approx(0.75)
    assert row["risk_level"] == "red"
    assert row["driver"] == "both"


def test_bucket_boundaries():
    risk = score(
        [("A", 0.0, False, False), ("B", 0.0, False, False), ("C", 0.0, False, False)],
        [("A", 75.9), ("B", 76.0), ("C", 88.0)],  # overload 0.3975, 0.4, 0.7
    )
    assert risk.loc["A", "risk_level"] == "green"
    assert risk.loc["B", "risk_level"] == "amber"
    assert risk.loc["C", "risk_level"] == "red"


def test_weights_scale_each_signal():
    row = score(
        [("T1", 0.25, True, False)], [("T1", 0.0)], loss_weight=0.5
    ).loc["T1"]
    assert row["risk_score"] == pytest.approx(0.5)
    assert row["risk_level"] == "amber"


def test_transformer_missing_from_one_input_is_kept():
    risk = score([("T1", 0.25, True, False)], [("T2", 95.0)])
    assert risk.loc["T1", "has_loss_data"] and not risk.loc["T1", "has_forecast"]
    assert risk.loc["T2", "has_forecast"] and not risk.loc["T2", "has_loss_data"]
    assert risk.loc["T2", "risk_level"] == "red"


def test_sorted_highest_risk_first():
    risk = score_transformers(
        flags([("T1", 0.0, False, False), ("T2", 0.25, True, False)]),
        forecast([("T1", 0.0), ("T2", 0.0)]),
    )
    assert list(risk["transformer_id"]) == ["T2", "T1"]


def test_missing_columns_raise():
    with pytest.raises(ValueError, match="mean_gap"):
        score_transformers(pd.DataFrame({"transformer_id": ["T1"]}), forecast([("T1", 50.0)]))


def test_evaluate_risk():
    risk = pd.DataFrame(
        {
            "transformer_id": ["T1", "T2", "T3", "T4"],
            "risk_level": ["red", "amber", "green", "red"],
        }
    )
    result = evaluate_risk(risk, true_ids=["T1", "T2", "T3"])
    assert result["illegal_caught"] == pytest.approx(0.667)
    assert result["illegal_red"] == pytest.approx(0.333)
    assert result["normal_red"] == 1.0
    assert result["counts"] == {"green": 1, "amber": 1, "red": 2}
