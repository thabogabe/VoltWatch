-- Runs automatically on first start of the PostGIS container (docker-compose),
-- or manually: psql "$DATABASE_URL" -f db/init.sql
-- Tables are created from backend/app/models.py: python -m app.create_tables

CREATE EXTENSION IF NOT EXISTS postgis;
