from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from . import models
from .db import get_db, engine

app = FastAPI(title="VoltWatch API")

# Allow the Vite frontend (usually http://localhost:5173) to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "GridGuard API is running"}

@app.get("/transformers")
def get_transformers(db: Session = Depends(get_db)):
    """Returns all transformers with risk scores for the frontend map."""
    transformers = db.query(models.Transformer).all()
    result = []
    
    for t in transformers:
        result.append({
            "id": t.id,
            "lat": t.lat,
            "lon": t.lon,
            "capacity_kva": getattr(t, 'capacity_kva', 100),
            "ward": getattr(t, 'ward', 'Soweto'),
            "risk_level": getattr(t, 'risk_level', 'green'),
            "risk_score": getattr(t, 'risk_score', 0.0),
            "loss_score": getattr(t, 'loss_score', 0.0),
            "overload_score": getattr(t, 'overload_score', 0.0),
            "utilization_pct": getattr(t, 'utilization_pct', 0.0),
            "driver": getattr(t, 'driver', 'none')
        })
    return result

@app.get("/transformers/{transformer_id}")
def get_transformer(transformer_id: str, db: Session = Depends(get_db)):
    """Returns detailed stats, history, and forecast for a single transformer."""
    t = db.query(models.Transformer).filter(models.Transformer.id == transformer_id).first()
    
    if not t:
        raise HTTPException(status_code=404, detail="Transformer not found")
    
    # Calculate connected customers
    customer_count = db.query(models.Customer).filter(models.Customer.transformer_id == transformer_id).count()
    indigent_count = db.query(models.Customer).filter(
        models.Customer.transformer_id == transformer_id,
        models.Customer.is_indigent == True
    ).count()

    # Retrieve history using raw SQL to align with load_monthly_balance logic
    # Groups daily readings and billing into monthly aggregates, sorted oldest first
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
        loss_pct = ((supplied - billed) / supplied * 100) if supplied > 0 else 0.0
        
        history.append({
            "month": row.month,
            "supplied_kwh": round(supplied, 2),
            "billed_kwh": round(billed, 2),
            "unexplained_loss_pct": round(loss_pct, 2),
            "peak_kva": round(float(row.peak_kva), 2) if row.peak_kva else 0.0
        })

    return {
        "id": t.id,
        "lat": t.lat,
        "lon": t.lon,
        "capacity_kva": getattr(t, 'capacity_kva', 100),
        "ward": getattr(t, 'ward', 'Soweto'),
        "risk_level": getattr(t, 'risk_level', 'green'),
        "risk_score": getattr(t, 'risk_score', 0.0),
        "loss_score": getattr(t, 'loss_score', 0.0),
        "overload_score": getattr(t, 'overload_score', 0.0),
        "utilization_pct": getattr(t, 'utilization_pct', 0.0),
        "driver": getattr(t, 'driver', 'none'),
        "customer_count": customer_count,
        "indigent_count": indigent_count,
        "history": history,
        "forecast": {
            "month": "2026-09",
            "predicted_peak_kva": getattr(t, 'predicted_peak_kva', 0.0),
            "utilization_pct": getattr(t, 'next_month_utilization', 0.0),
            "at_risk": getattr(t, 'at_risk', False)
        }
    }

@app.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """Returns headline metrics for the dashboard banner."""
    return {
        "total_transformers": db.query(models.Transformer).count(),
        "total_customers": db.query(models.Customer).count(),
        "households_regularised": 42, # Mock value until queue logic is built
        "outages_avoided": 7          # Mock value until queue logic is built
    }