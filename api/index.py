"""Vercel entry point: serves the FastAPI app (backend/app/main.py) under /api.

The frontend is served from the same deployment, so the map calls /api/transformers etc.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi import FastAPI  # noqa: E402

from app.main import app as voltwatch_api  # noqa: E402

app = FastAPI()
app.mount("/api", voltwatch_api)
