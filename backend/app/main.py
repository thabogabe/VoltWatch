from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd
from pathlib import Path
from . import models
from .db import get_session, engine

app = FastAPI(title="VoltWatch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

def load_risk_data():
    """Helper to load Step 6 risk outputs into a dictionary for fast lookup."""
    csv_path = DATA_DIR / "risk.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        return df.set_index('transformer_id').to_dict('index')
    return {}

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "GridGuard API is running"}

@app.get("/transformers")
def get_transformers(db: Session = Depends(get_session)):
    """Returns all transformers with real risk scores for the frontend map."""
    transformers = db.query(models.Transformer).all()
    risk_dict = load_risk_data()
    
    result = []
    for t in transformers:
        r = risk_dict.get(t.id, {})
        result.append({
            "id": t.id,
            "lat": t.lat,
            "lon": t.lon,
            "capacity_kva": getattr(t, 'capacity_kva', 100),
            "ward": getattr(t, 'ward', 'Soweto'),
            "risk_level": r.get('risk_level', 'green'),
            "risk_score": r.get('risk_score', 0.0),
            "loss_score": r.get('loss_score', 0.0),
            "overload_score": r.get('overload_score', 0.0),
            "utilization_pct": r.get('utilization_pct', 0.0),
            "driver": r.get('driver', 'none')
        })
    return result

@app.get("/transformers/{transformer_id}")
def get_transformer(transformer_id: str, db: Session = Depends(get_session)):
    """Returns detailed stats, history, and forecast for a single transformer."""
    t = db.query(models.Transformer).filter(models.Transformer.id == transformer_id).first()
    
    if not t:
        raise HTTPException(status_code=404, detail="Transformer not found")
    
    risk_dict = load_risk_data()
    r = risk_dict.get(transformer_id, {})
    
    customer_count = db.query(models.Customer).filter(models.Customer.transformer_id == transformer_id).count()
    indigent_count = db.query(models.Customer).filter(
        models.Customer.transformer_id == transformer_id,
        models.Customer.is_indigent == True
    ).count()

    history_query = text("""
        SELECT 
            TO_CHAR(r.reading_date, 'YYYY-MM') AS month,
            SUM(r.energy_kwh) AS supplied_kwh,
            MAX(r.peak_kva) AS peak_kva,
            COALESCE((
                SELECT SUM(b.kwh_billed) 
                FROM billing b 
                JOIN customers c ON b.customer_id = c.id 
                WHERE c.transformer_id = :tid 
                AND b.billing_month = DATE_TRUNC('month', r.reading_date)
            ), 0) AS billed_kwh
        FROM transformer_readings r
        WHERE r.transformer_id = :tid
        GROUP BY TO_CHAR(r.reading_date, 'YYYY-MM'), DATE_TRUNC('month', r.reading_date)
        ORDER BY month ASC
    """)
    
    history_records = db.execute(history_query, {"tid": transformer_id}).fetchall()
    
    history = []
    for row in history_records:
        supplied = float(row.supplied_kwh) if row.supplied_kwh else 0.0
        billed = float(row.billed_kwh)
        
        # Step 3 fraction: Total loss fraction minus an estimated 6.5% technical loss
        total_loss_frac = (supplied - billed) / supplied if supplied > 0 else 0.0
        unexplained_loss_frac = max(0.0, total_loss_frac - 0.065)
        
        history.append({
            "month": row.month,
            "supplied_kwh": round(supplied, 2),
            "billed_kwh": round(billed, 2),
            "unexplained_loss_pct": round(unexplained_loss_frac, 4),
            "peak_kva": round(float(row.peak_kva), 2) if row.peak_kva else 0.0
        })

    return {
        "id": t.id,
        "lat": t.lat,
        "lon": t.lon,
        "capacity_kva": getattr(t, 'capacity_kva', 100),
        "ward": getattr(t, 'ward', 'Soweto'),
        "risk_level": r.get('risk_level', 'green'),
        "risk_score": r.get('risk_score', 0.0),
        "loss_score": r.get('loss_score', 0.0),
        "overload_score": r.get('overload_score', 0.0),
        "utilization_pct": r.get('utilization_pct', 0.0),
        "driver": r.get('driver', 'none'),
        "customer_count": customer_count,
        "indigent_count": indigent_count,
        "history": history,
        "forecast": {
            "month": "2026-09",
            "predicted_peak_kva": r.get('predicted_peak_kva', 0.0),
            "utilization_pct": r.get('utilization_pct', 0.0),
            "at_risk": r.get('at_risk', False)
        }
    }

@app.get("/summary")
def get_summary(db: Session = Depends(get_session)):
    """Returns headline metrics and dynamic risk counts for the dashboard banner."""
    risk_dict = load_risk_data()
    levels = [r.get('risk_level', 'green') for r in risk_dict.values()]
    
    return {
        "total_transformers": db.query(models.Transformer).count(),
        "total_customers": db.query(models.Customer).count(),
        "risk_counts": {
            "green": levels.count('green'),
            "amber": levels.count('amber'),
            "red": levels.count('red')
        }
    }