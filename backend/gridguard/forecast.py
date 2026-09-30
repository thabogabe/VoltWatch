import pandas as pd
import xgboost as xgb
import os

def run_forecast():
    print("Training XGBoost forecast model...")
    
    # 1. Load data
    readings = pd.read_csv("../../data/transformer_readings.csv")
    transformers = pd.read_csv("../../data/transformers.csv")
    
    # Ensure sequential chronological sorting
    readings['reading_date'] = pd.to_datetime(readings['reading_date'])
    readings = readings.sort_values(by=['transformer_id', 'reading_date'])
    
    # 2. Feature Engineering: Create Lag Features (previous 2 months of load)
    readings['lag_1'] = readings.groupby('transformer_id')['energy_kwh'].shift(1)
    readings['lag_2'] = readings.groupby('transformer_id')['energy_kwh'].shift(2)
    
    # Drop rows with NaNs (the first two months of the synthetic timeline) to create a clean training set
    train_df = readings.dropna().copy()
    
    features = ['lag_1', 'lag_2']
    target = 'energy_kwh'
    
    X_train = train_df[features]
    y_train = train_df[target]
    
    # 3. Train the XGBoost Regressor
    model = xgb.XGBRegressor(
        objective='reg:squarederror', 
        n_estimators=100, 
        learning_rate=0.1,
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # 4. Prepare next-month prediction data
    # Extract the two most recent months for each transformer to act as the new lag_1 and lag_2
    latest_readings = readings.groupby('transformer_id').tail(2)
    
    forecast_data = []
    for tx_id, group in latest_readings.groupby('transformer_id'):
        if len(group) == 2:
            lag_2_val = group.iloc[0]['energy_kwh']
            lag_1_val = group.iloc[1]['energy_kwh']
            forecast_data.append({
                'transformer_id': tx_id, 
                'lag_1': lag_1_val, 
                'lag_2': lag_2_val
            })
            
    forecast_df = pd.DataFrame(forecast_data)
    
    # 5. Execute Next-Month Forecast
    forecast_df['predicted_next_month_kwh'] = model.predict(forecast_df[features])
    
    # 6. Calculate Utilization & Apply >90% Risk Flag
    results = forecast_df.merge(transformers[['transformer_id', 'capacity_kwh']], on='transformer_id')
    results['utilization_pct'] = (results['predicted_next_month_kwh'] / results['capacity_kwh']) * 100
    
    # Boolean flag strictly applying the >90% business rule
    results['at_risk'] = results['utilization_pct'] > 90.0
    
    # Format for output
    results = results[['transformer_id', 'capacity_kwh', 'predicted_next_month_kwh', 'utilization_pct', 'at_risk']]
    results['utilization_pct'] = results['utilization_pct'].round(2)
    results['predicted_next_month_kwh'] = results['predicted_next_month_kwh'].round(2)
    
    os.makedirs("../../data", exist_ok=True)
    results.to_csv("../../data/forecast_results.csv", index=False)
    
    at_risk_count = results['at_risk'].sum()
    print(f"Forecast complete! Identified {at_risk_count} transformers at >90% capacity risk for next month.")
    print("Results saved to /data/forecast_results.csv")

if __name__ == "__main__":
    run_forecast()