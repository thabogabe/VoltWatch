# VoltWatch (GridGuard)

GridGuard compares how much power each transformer supplies with how much its registered customers are billed for. A large gap that persists over time flags the transformer as likely to have illegal connections. GridGuard also predicts which transformers are closest to overloading, so they can be dealt with before they fail.

Transformers are shown on an interactive map, coloured green, amber or red by risk, so utility teams can decide where to inspect first.

The goal is to protect communities, not punish them. A red flag sends an area to a **regularisation queue**: legal connection drives, prepaid meter installation, and Free Basic Electricity registration for indigent households. All analysis stays at **transformer level**, so no household is ever singled out (POPIA).

## Stack

| Layer    | Tech |
|----------|------|
| Data/ML  | Python, pandas, scikit-learn (Isolation Forest), XGBoost |
| Database | PostgreSQL + PostGIS |
| API      | FastAPI |
| Frontend | React (Vite), Leaflet, Recharts |
| Deploy   | Render/Railway (API + DB), Vercel (frontend) |

## Layout

```
backend/
  app/         FastAPI app (config, db, models, endpoints)
  gridguard/   analytics pipeline: generate, losses, flags, forecast, risk
  tests/
db/init.sql    database init (PostGIS)
frontend/      React + Leaflet map
data/          generated synthetic data (git-ignored)
```

## Setup

Prerequisites: Python 3.12+, Node 20+, and either Docker Desktop or a Postgres database with PostGIS enabled (for example Neon or Supabase).

### 1. Database

```bash
docker compose up -d db          # starts PostGIS
```

If you use a hosted Postgres instead, run `db/init.sql` against it and put its URL in `backend/.env`.

### 2. Backend

```powershell
cd backend
py -m venv .venv
.venv\Scripts\activate           # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # then edit DATABASE_URL if needed
python -m app.create_tables      # create the tables (needs the database running)
uvicorn app.main:app --reload    # http://localhost:8000/docs
pytest
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

## Roadmap

1. [x] Data model (`backend/app/models.py`): transformers, customers, transformer_readings, billing
2. [ ] Synthetic data generator with ~10% injected illegal load (ground truth)
3. [ ] Loss calculation net of 5–8% technical loss
4. [ ] Persistent-gap flag (3+ consecutive months) and Isolation Forest vs neighbours
5. [ ] XGBoost next-month peak forecast; >90% utilisation = at risk
6. [ ] Combined risk score: green < 0.4, amber 0.4–0.7, red > 0.7
7. [ ] API: `/transformers`, `/transformers/{id}`, `/summary`
8. [ ] Map: coloured markers, supplied vs billed chart, overload forecast
9. [ ] Deploy

Headline metrics: **households moved onto legal connections** and **outages avoided**.
