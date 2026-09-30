"""Run step 4 from the command line (from the backend/ folder):

    python -m gridguard.run_flagging

Reads the step 2 generator output from the repo-level data/ folder, builds the
monthly losses with step 3 (monthly_balance) and writes data/flags.csv:
    data/transformers.csv, customers.csv, billing.csv, transformer_readings.csv

If data/ground_truth.csv exists (transformer_id, has_illegal_load, from step 2),
precision/recall against the injected illegal load is printed as well.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from gridguard.flagging import FlagConfig, evaluate_flags, flag_transformers
from gridguard.losses import monthly_balance

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def main() -> None:
    p = argparse.ArgumentParser(description="Flag persistent loss gaps and anomalies.")
    p.add_argument("--data", type=Path, default=DATA_DIR, help="folder with the step 2 CSVs")
    p.add_argument("--out", type=Path, default=None, help="default: <data>/flags.csv")
    p.add_argument("--threshold", type=float, default=FlagConfig.gap_threshold)
    p.add_argument("--months", type=int, default=FlagConfig.min_consecutive_months)
    p.add_argument("--contamination", type=float, default=FlagConfig.contamination)
    p.add_argument("--require-current", action="store_true")
    args = p.parse_args()

    transformers = pd.read_csv(args.data / "transformers.csv")
    if "id" not in transformers.columns:  # generator CSVs may still use transformer_id
        transformers = transformers.rename(columns={"transformer_id": "id"})
    losses = monthly_balance(
        readings=pd.read_csv(args.data / "transformer_readings.csv"),
        billing=pd.read_csv(args.data / "billing.csv"),
        customers=pd.read_csv(args.data / "customers.csv"),
    )

    cfg = FlagConfig(
        gap_threshold=args.threshold,
        min_consecutive_months=args.months,
        contamination=args.contamination,
        require_current=args.require_current,
    )
    flags = flag_transformers(losses, transformers, cfg)

    out = args.out or args.data / "flags.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    flags.to_csv(out, index=False)

    print(f"{len(flags)} transformers analysed")
    print(flags["flag_reason"].value_counts().to_string())
    print(f"saved -> {out}")

    truth_file = args.data / "ground_truth.csv"
    if truth_file.exists():
        truth = pd.read_csv(truth_file)
        truth_ids = truth.loc[truth["has_illegal_load"].astype(bool), "transformer_id"]
        for col in ("persistent_flag", "anomaly_flag", "flagged"):
            print(evaluate_flags(flags, truth_ids, column=col))


if __name__ == "__main__":
    main()
