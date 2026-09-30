"""Run step 4 from the command line (from the backend/ folder):

    python -m gridguard.run_flagging

Defaults read/write the repo-level data/ folder:
    ../data/monthly_losses.csv    (step 3 output: transformer_id, month, unexplained_gap)
    ../data/transformers.csv      (transformer_id, lat, lon, ...)
    ../data/flags.csv             (written by this script)

Optional: pass --truth ../data/illegal_transformers.csv (a CSV with a
transformer_id column, from the step 2 generator) to print precision/recall.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from gridguard.flagging import FlagConfig, evaluate_flags, flag_transformers


def main() -> None:
    p = argparse.ArgumentParser(description="Flag persistent loss gaps and anomalies.")
    p.add_argument("--losses", default="../data/monthly_losses.csv")
    p.add_argument("--transformers", default="../data/transformers.csv")
    p.add_argument("--out", default="../data/flags.csv")
    p.add_argument("--truth", default=None, help="CSV with transformer_id of injected illegal load")
    p.add_argument("--threshold", type=float, default=FlagConfig.gap_threshold)
    p.add_argument("--months", type=int, default=FlagConfig.min_consecutive_months)
    p.add_argument("--contamination", type=float, default=FlagConfig.contamination)
    p.add_argument("--require-current", action="store_true")
    args = p.parse_args()

    losses = pd.read_csv(args.losses)
    transformers = pd.read_csv(args.transformers)

    cfg = FlagConfig(
        gap_threshold=args.threshold,
        min_consecutive_months=args.months,
        contamination=args.contamination,
        require_current=args.require_current,
    )
    flags = flag_transformers(losses, transformers, cfg)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    flags.to_csv(out, index=False)

    print(f"{len(flags)} transformers analysed")
    print(flags["flag_reason"].value_counts().to_string())
    print(f"saved -> {out}")

    if args.truth:
        truth_ids = pd.read_csv(args.truth)["transformer_id"]
        for col in ("persistent_flag", "anomaly_flag", "flagged"):
            print(evaluate_flags(flags, truth_ids, column=col))


if __name__ == "__main__":
    main()
