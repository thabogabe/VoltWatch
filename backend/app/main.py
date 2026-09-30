from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import settings

app = FastAPI(
    title="VoltWatch API",
    description="GridGuard: transformer-level loss and overload risk.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "database": "up" if db.ping() else "down"}


# Step 7 endpoints (to be implemented):
#   GET /transformers        -> all transformers with risk colour
#   GET /transformers/{id}   -> supplied vs billed history + overload forecast
#   GET /summary             -> counts by risk level
