from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models
from .db import get_db

app = FastAPI(title="VoltWatch API")

# Allow the Vite frontend (usually http://localhost:5173) to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update to frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "VoltWatch API is running"}

@app.get("/transformers")
def get_transformers(db: Session = Depends(get_db)):
    """Returns all transformers to populate the Leaflet map markers."""
    transformers = db.query(models.Transformer).all()
    return transformers

@app.get("/transformers/{transformer_id}")
def get_transformer(transformer_id: str, db: Session = Depends(get_db)):
    """Returns detailed stats for a single transformer when clicked on the map."""
    transformer = db.query(models.Transformer).filter(models.Transformer.id == transformer_id).first()
    
    if not transformer:
        raise HTTPException(status_code=404, detail="Transformer not found")
    
    # Calculate connected customers using the relationships from Step 2
    customer_count = db.query(models.Customer).filter(models.Customer.transformer_id == transformer_id).count()
    indigent_count = db.query(models.Customer).filter(
        models.Customer.transformer_id == transformer_id,
        models.Customer.is_indigent == True
    ).count()

    return {
        "id": transformer.id,
        "lat": transformer.lat,
        "lon": transformer.lon,
        "capacity_kva": transformer.capacity_kva,
        "total_customers": customer_count,
        "indigent_customers": indigent_count
    }

@app.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """Returns headline metrics for the dashboard banner."""
    total_transformers = db.query(models.Transformer).count()
    total_customers = db.query(models.Customer).count()
    
    # Returns 0 as placeholders for the headline metrics listed in the README
    return {
        "total_transformers": total_transformers,
        "total_customers": total_customers,
        "households_regularised": 0, 
        "outages_avoided": 0         
    }