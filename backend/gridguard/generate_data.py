import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from pathlib import Path

# Dynamically resolve absolute path to VoltWatch/data
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

# Configuration
NUM_TRANSFORMERS = 100
CUSTOMERS_PER_TRANSFORMER = 20
DAYS = 365
START_DATE = datetime(2025, 9, 1)

LAT_MIN, LAT_MAX = -26.30, -26.20
LON_MIN, LON_MAX = 27.80, 27.90

# Fixed seed so everyone on the team generates the same dataset
SEED = 42

# Each illegal-load transformer gets its own theft severity (extra load as a share
# of legal load) and a day it starts, so the cases range from small/recent to
# large/long-running instead of all looking identical.
ILLEGAL_SEVERITY = (0.10, 0.70)
ILLEGAL_LATEST_START_DAY = 240  # still leaves 4+ months of losses to detect

def generate_synthetic_data():
    print("Generating daily VoltWatch synthetic data with seasonality...")
    random.seed(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Transformers (exactly 10% get injected illegal load: the ground truth)
    illegal_ids = set(random.sample(range(1, NUM_TRANSFORMERS + 1), NUM_TRANSFORMERS // 10))
    transformers = []
    for i in range(1, NUM_TRANSFORMERS + 1):
        transformers.append({
            "id": f"TX_{i:03d}",
            "lat": random.uniform(LAT_MIN, LAT_MAX),
            "lon": random.uniform(LON_MIN, LON_MAX),
            "capacity_kva": random.choice([50, 100, 200, 315]),
            "has_illegal_load": i in illegal_ids,
            "illegal_severity": random.uniform(*ILLEGAL_SEVERITY),
            "illegal_start_day": random.randint(0, ILLEGAL_LATEST_START_DAY),
        })
    df_transformers = pd.DataFrame(transformers)

    # 2. Customers
    customers = []
    customer_id_counter = 1
    for _, tx in df_transformers.iterrows():
        for _ in range(CUSTOMERS_PER_TRANSFORMER):
            customers.append({
                "id": f"CUST_{customer_id_counter:05d}",
                "transformer_id": tx["id"],
                "is_indigent": random.choices([True, False], weights=[0.2, 0.8])[0]
            })
            customer_id_counter += 1
    df_customers = pd.DataFrame(customers)

    # 3. Daily Simulation (Readings & Billing)
    readings = []
    billing_records = []
    
    for d in range(DAYS):
        current_date = START_DATE + timedelta(days=d)
        formatted_date = current_date.strftime("%Y-%m-%d")
        billing_month = current_date.strftime("%Y-%m-01")
        
        # Simulate Southern Hemisphere seasonality (hottest in Jan, coldest in Jul)
        month_num = current_date.month
        temp = 17.5 + 7.5 * np.cos((month_num - 1) * np.pi / 6) + random.uniform(-2, 2)
        
        # Base daily kWh increases as temperature drops
        base_household_kwh = 8 + (25 - temp) * 0.4
        
        for _, tx in df_transformers.iterrows():
            tx_customers = df_customers[df_customers["transformer_id"] == tx["id"]]
            total_legal_daily_kwh = 0
            
            for _, cust in tx_customers.iterrows():
                # Gaussian noise for daily household variation
                usage = max(1.0, random.gauss(base_household_kwh, 2.0))
                total_legal_daily_kwh += usage
                
                billing_records.append({
                    "customer_id": cust["id"],
                    "billing_month": billing_month,
                    "kwh_billed": usage
                })
            
            # Add standard 5-8% technical loss
            supplied_kwh = total_legal_daily_kwh / (1 - random.uniform(0.05, 0.08))
            
            # Illegal load from its start day, at this transformer's own severity
            # (day-to-day noise, and higher during colder periods)
            if tx["has_illegal_load"] and d >= tx["illegal_start_day"]:
                theft_multiplier = (
                    tx["illegal_severity"] * random.uniform(0.7, 1.3) + (25 - temp) * 0.01
                )
                supplied_kwh += total_legal_daily_kwh * theft_multiplier
            
            # Heuristic conversion: daily energy to peak kVA
            # peak kW = (daily kWh / 24) / load_factor. Assumed power factor = 0.9
            load_factor = random.uniform(0.3, 0.5)
            peak_kw = (supplied_kwh / 24) / load_factor
            peak_kva = peak_kw / 0.90
            
            readings.append({
                "transformer_id": tx["id"],
                "reading_date": formatted_date,
                "energy_kwh": round(supplied_kwh, 2),
                "peak_kva": round(peak_kva, 2),
                "temperature_c": round(temp, 1)
            })

    # Aggregate daily billing into monthly totals
    df_billing_daily = pd.DataFrame(billing_records)
    df_billing = df_billing_daily.groupby(["customer_id", "billing_month"])["kwh_billed"].sum().reset_index()
    df_billing["kwh_billed"] = df_billing["kwh_billed"].round(2)

    df_readings = pd.DataFrame(readings)

    # Clean up ground truth before saving
    truth_columns = ["has_illegal_load", "illegal_severity", "illegal_start_day"]
    df_transformers_clean = df_transformers.drop(columns=truth_columns)

    # Export
    df_transformers_clean.to_csv(DATA_DIR / "transformers.csv", index=False)
    df_customers.to_csv(DATA_DIR / "customers.csv", index=False)
    df_billing.to_csv(DATA_DIR / "billing.csv", index=False)
    df_readings.to_csv(DATA_DIR / "transformer_readings.csv", index=False)
    
    truth = df_transformers[["id", *truth_columns]].copy()
    truth.loc[~truth["has_illegal_load"], ["illegal_severity", "illegal_start_day"]] = None
    truth.to_csv(DATA_DIR / "ground_truth.csv", index=False)
    print(f"Data generated successfully with DB-compliant schema in {DATA_DIR}")

if __name__ == "__main__":
    generate_synthetic_data()