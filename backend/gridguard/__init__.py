"""GridGuard analytics pipeline.

Planned modules:
    generate.py  - synthetic data generator with injected illegal load (ground truth)
    losses.py    - supplied vs billed loss, net of expected technical loss
    flags.py     - persistent-gap rule (3+ months) and Isolation Forest
    forecast.py  - XGBoost next-month peak / utilisation forecast
    risk.py      - combined risk score and green/amber/red buckets
"""
