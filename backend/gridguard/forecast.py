import pandas as pd
import xgboost as xgb
from pathlib import Path

# Dynamically resolve absolute path to VoltWatch/data
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

def run_forecast():
    print("Training XGBoost forecast model on peak kVA...")
    
    # 1. Load data
    readings = pd.read_csv(DATA_DIR / "transformer_readings.csv")
    transformers = pd.read_csv(DATA_DIR / "transformers.csv")
    
    readings['reading_date'] = pd.to_datetime(readings['reading_date'])
    
    # 2. Extract highest peak_kva per transformer, per month
    readings['month_start'] = readings['reading_date'].dt.to_period('M').dt.to_timestamp()
    monthly_peaks = readings.groupby(['transformer_id', 'month_start'])['peak_kva'].max().reset_index()
    monthly_peaks = monthly_peaks.sort_values(by=['transformer_id', 'month_start'])
    
    # 3. Feature Engineering: Create Lag Features
    monthly_peaks['lag_1'] = monthly_peaks.groupby('transformer_id')['peak_kva'].shift(1)
    monthly_peaks['lag_2'] = monthly_peaks.groupby('transformer_id')['peak_kva'].shift(2)
    
    train_df = monthly_peaks.dropna().copy()
    
    features = ['lag_1', 'lag_2']
    target = 'peak_kva'
    
    X_train = train_df[features]
    y_train = train_df[target]
    
    # 4. Train Model
    model = xgb.XGBRegressor(
        objective='reg:squarederror', 
        n_estimators=100, 
        learning_rate=0.1,
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # 5. Prepare prediction data (most recent 2 months)
    latest_readings = monthly_peaks.groupby('transformer_id').tail(2)
    
    forecast_data = []
    for tx_id, group in latest_readings.groupby('transformer_id'):
        if len(group) == 2:
            lag_2_val = group.iloc[0]['peak_kva']
            lag_1_val = group.iloc[1]['peak_kva']
            forecast_data.append({
                'transformer_id': tx_id, 
                'lag_1': lag_1_val, 
                'lag_2': lag_2_val
            })
            
    forecast_df = pd.DataFrame(forecast_data)
    
    # 6. Predict and calculate True kVA Utilization
    forecast_df['predicted_peak_kva'] = model.predict(forecast_df[features])
    results = forecast_df.merge(transformers[['id', 'capacity_kva']], left_on='transformer_id', right_on='id')
    
    # Peak Load (kVA) / Capacity (kVA)
    results['utilization_pct'] = (results['predicted_peak_kva'] / results['capacity_kva']) * 100
    results['at_risk'] = results['utilization_pct'] > 90.0
    
    results = results[['transformer_id', 'capacity_kva', 'predicted_peak_kva', 'utilization_pct', 'at_risk']]
    results['utilization_pct'] = results['utilization_pct'].round(2)
    results['predicted_peak_kva'] = results['predicted_peak_kva'].round(2)
    
    results.to_csv(DATA_DIR / "forecast_results.csv", index=False)
    
    at_risk_count = results['at_risk'].sum()
    print(f"Forecast complete! Identified {at_risk_count} transformers at >90% kVA capacity risk for next month.")

if __name__ == "__main__":
    run_forecast()