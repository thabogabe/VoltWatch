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

If you use a hosted Postgres instead (e.g. Supabase), put its URL in `backend/.env` as
`postgresql+psycopg://...?sslmode=require`. If that database is shared with another app, also set
`DB_SCHEMA=voltwatch`: the tables and PostGIS then go into their own schema and the other app's
`public` schema is left untouched. Remove it all with `DROP SCHEMA voltwatch CASCADE`.

### 2. Backend

```powershell
cd backend
py -m venv .venv
.venv\Scripts\activate           # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # then edit DATABASE_URL if needed
pytest
```

Generate the data, run the analysis, load the database and start the API (from `backend/`):

```powershell
python gridguard/generate_data.py   # step 2 -> data/*.csv (takes ~40 s)
python -m gridguard.run_flagging    # steps 3-4 -> data/flags.csv
python gridguard/forecast.py        # step 5 -> data/forecast_results.csv
python -m gridguard.risk            # step 6 -> data/risk.csv
python -m app.load_data             # create tables and load data/*.csv into Postgres
uvicorn app.main:app --reload       # http://localhost:8000/docs
```

The API reads transformers, customers, readings and billing from Postgres, and the
risk and forecast results from `data/risk.csv` and `data/forecast_results.csv`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

## Deploy (Vercel)

One Vercel project serves both parts: the map (`frontend/`, built to static files) and the
API as a Python function under `/api` (`api/index.py` mounts `backend/app/main.py`).
Config: `vercel.json`, `.vercelignore`, and the root `requirements.txt` (API packages only;
XGBoost and scikit-learn are too large for a function and are only needed for the pipeline).

1. Run the pipeline locally so `data/risk.csv` and `data/forecast_results.csv` exist
   (they are uploaded with the deploy; everything else in `data/` is not).
2. In the Vercel project settings, add the environment variables `DATABASE_URL` and
   `DB_SCHEMA` (same values as `backend/.env`).
3. `npx vercel deploy --prod` from the repo root.

The function runs in Paris (`cdg1`), next to the Supabase database.

## Roadmap

1. [x] Data model (`backend/app/models.py`): transformers, customers, transformer_readings, billing
2. [x] Synthetic data generator with ~10% injected illegal load (ground truth) (`backend/gridguard/generate_data.py`)
3. [x] Loss calculation net of 5–8% technical loss (`backend/gridguard/losses.py`)
4. [x] Persistent-gap flag (3+ consecutive months) and Isolation Forest vs neighbours (`backend/gridguard/flagging.py`)
5. [x] XGBoost next-month peak forecast; >90% utilisation = at risk (`backend/gridguard/forecast.py`)
6. [x] Combined risk score: green < 0.4, amber 0.4–0.7, red > 0.7 (`backend/gridguard/risk.py`)
7. [x] API: `/transformers`, `/transformers/{id}`, `/summary` (`backend/app/main.py`, loader `backend/app/load_data.py`)
8. [x] Map: coloured markers, supplied vs billed chart, overload forecast (`frontend/src`)
9. [ ] Deploy

Headline metrics: **households moved onto legal connections** and **outages avoided**.
