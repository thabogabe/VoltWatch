import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import os

# Configuration
NUM_TRANSFORMERS = 100
CUSTOMERS_PER_TRANSFORMER = 20
MONTHS = 12
START_DATE = datetime(2025, 9, 1)

# Soweto approximate bounding box for realistic PostGIS plotting
LAT_MIN, LAT_MAX = -26.30, -26.20
LON_MIN, LON_MAX = 27.80, 27.90

def generate_synthetic_data():
    print("Generating VoltWatch synthetic data...")
    
    # 1. Transformers
    transformers = []
    for i in range(1, NUM_TRANSFORMERS + 1):
        transformers.append({
            "transformer_id": f"TX_{i:03d}",
            "lat": random.uniform(LAT_MIN, LAT_MAX),
            "lon": random.uniform(LON_MIN, LON_MAX),
            "capacity_kwh": random.choice([5000, 10000, 15000]),
            # Ground truth flag for the 10% injected illegal load
            "has_illegal_load": random.random() < 0.10  
        })
    df_transformers = pd.DataFrame(transformers)

    # 2. Customers
    customers = []
    customer_id_counter = 1
    for _, tx in df_transformers.iterrows():
        for _ in range(CUSTOMERS_PER_TRANSFORMER):
            customers.append({
                "id": f"CUST_{customer_id_counter:05d}",
                "transformer_id": tx["transformer_id"]
            })
            customer_id_counter += 1
    df_customers = pd.DataFrame(customers)

    # 3 & 4. Billing and Transformer Readings
    billing = []
    readings = []
    
    for month_offset in range(MONTHS):
        current_date = START_DATE + pd.DateOffset(months=month_offset)
        # Standardize date format for Postgres DATE columns
        formatted_date = current_date.strftime("%Y-%m-%d")
        
        for _, tx in df_transformers.iterrows():
            tx_customers = df_customers[df_customers["transformer_id"] == tx["transformer_id"]]
            total_billed_kwh = 0
            
            # Generate billing for each customer
            for _, cust in tx_customers.iterrows():
                # Base household usage (e.g., 150 - 400 kWh per month)
                usage = round(random.uniform(150, 400), 2)
                total_billed_kwh += usage
                
                billing.append({
                    "customer_id": cust["id"],
                    "billing_month": formatted_date,
                    "kwh_billed": usage
                })
            
            # Calculate transformer supplied power
            # Add base 5% to 8% technical loss
            technical_loss_rate = random.uniform(0.05, 0.08) 
            supplied_kwh = total_billed_kwh / (1 - technical_loss_rate)
            
            # Inject illegal load for flagged transformers
            if tx["has_illegal_load"]:
                # Inject a massive spike (e.g., 40-60% extra load not accounted for in billing)
                illegal_spike = supplied_kwh * random.uniform(0.40, 0.60)
                supplied_kwh += illegal_spike
                
            readings.append({
                "transformer_id": tx["transformer_id"],
                "reading_date": formatted_date,
                "energy_kwh": round(supplied_kwh, 2)
            })

    df_billing = pd.DataFrame(billing)
    df_readings = pd.DataFrame(readings)

    # Clean up ground truth column from transformers
    df_transformers_clean = df_transformers.drop(columns=["has_illegal_load"])

    # Save to data directory
    os.makedirs("../../data", exist_ok=True)
    df_transformers_clean.to_csv("../../data/transformers.csv", index=False)
    df_customers.to_csv("../../data/customers.csv", index=False)
    df_billing.to_csv("../../data/billing.csv", index=False)
    df_readings.to_csv("../../data/transformer_readings.csv", index=False)
    
    # Save a separate ground truth file
    df_transformers[["transformer_id", "has_illegal_load"]].to_csv("../../data/ground_truth.csv", index=False)
    
    print("Data generated successfully with DB-compliant columns in the /data directory.")

if __name__ == "__main__":
    generate_synthetic_data()