"""Community incident reports: residents report faults and cable theft, patrols respond.

POST  /reports        anyone, anonymous (no name, phone or address is accepted or stored)
GET   /reports        open reports for the map and the patrol board
PATCH /reports/{id}   patrol officers set the status; needs the X-Patrol-Code header
"""

import math
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_session
from .models import REPORT_CATEGORIES, REPORT_STATUSES, IncidentReport, Transformer

router = APIRouter(prefix="/reports", tags=["community reports"])

Category = Literal[REPORT_CATEGORIES]  # type: ignore[valid-type]
Status = Literal[REPORT_STATUSES]  # type: ignore[valid-type]

# Reports are only accepted inside the service area (Soweto and surroundings).
SERVICE_AREA = {"lat": (-26.40, -26.10), "lon": (27.70, 28.00)}
NEAREST_TRANSFORMER_MAX_KM = 1.0
# Ambiguous characters (0/O, 1/I) left out so codes are easy to read out over the phone.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class ReportIn(BaseModel):
    category: Category
    lat: float
    lon: float
    is_urgent: bool = False
    description: str | None = Field(default=None, max_length=500)

    @field_validator("lat")
    @classmethod
    def lat_in_area(cls, v: float) -> float:
        lo, hi = SERVICE_AREA["lat"]
        if not lo <= v <= hi:
            raise ValueError("location is outside the service area")
        return v

    @field_validator("lon")
    @classmethod
    def lon_in_area(cls, v: float) -> float:
        lo, hi = SERVICE_AREA["lon"]
        if not lo <= v <= hi:
            raise ValueError("location is outside the service area")
        return v

    @field_validator("description")
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        return v.strip() or None if v else None


class StatusIn(BaseModel):
    status: Status


def report_out(r: IncidentReport) -> dict:
    return {
        "id": r.id,
        "category": r.category,
        "lat": float(r.lat),
        "lon": float(r.lon),
        "transformer_id": r.transformer_id,
        "is_urgent": r.is_urgent,
        "description": r.description,
        "status": r.status,
        "created_at": _iso(r.created_at),
        "updated_at": _iso(r.updated_at),
    }


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):  # SQLite returns text
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def nearest_transformer(db_session: Session, lat: float, lon: float) -> str | None:
    rows = db_session.execute(select(Transformer.id, Transformer.lat, Transformer.lon)).all()
    best = min(
        ((_distance_km(lat, lon, float(t.lat), float(t.lon)), t.id) for t in rows),
        default=None,
    )
    if best is None or best[0] > NEAREST_TRANSFORMER_MAX_KM:
        return None
    return best[1]


def open_report_counts(db_session: Session, since_days: int = 30) -> dict[str, int]:
    """{transformer_id: number of open reports in the last `since_days` days}."""
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    rows = db_session.execute(
        select(IncidentReport.transformer_id, func.count())
        .where(
            IncidentReport.transformer_id.is_not(None),
            IncidentReport.status != "resolved",
            IncidentReport.created_at >= since,
        )
        .group_by(IncidentReport.transformer_id)
    ).all()
    return {tid: n for tid, n in rows}


@router.post("", status_code=201)
def create_report(report: ReportIn, db_session: Session = Depends(get_session)):
    row = IncidentReport(
        id="".join(secrets.choice(CODE_ALPHABET) for _ in range(6)),
        category=report.category,
        lat=report.lat,
        lon=report.lon,
        transformer_id=nearest_transformer(db_session, report.lat, report.lon),
        is_urgent=report.is_urgent,
        description=report.description,
        status="new",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return report_out(row)


@router.get("")
def list_reports(
    include_resolved: bool = False, days: int = 30, db_session: Session = Depends(get_session)
):
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))
    query = select(IncidentReport).where(IncidentReport.created_at >= since)
    if not include_resolved:
        query = query.where(IncidentReport.status != "resolved")
    rows = db_session.scalars(
        query.order_by(IncidentReport.is_urgent.desc(), IncidentReport.created_at.desc()).limit(300)
    ).all()
    return [report_out(r) for r in rows]


@router.patch("/{report_id}")
def update_status(
    report_id: str,
    update: StatusIn,
    x_patrol_code: str | None = Header(default=None),
    db_session: Session = Depends(get_session),
):
    if not settings.patrol_code:
        raise HTTPException(503, "Patrol updates are not set up (PATROL_CODE is empty)")
    if not x_patrol_code or not secrets.compare_digest(x_patrol_code, settings.patrol_code):
        raise HTTPException(403, "Wrong patrol code")
    row = db_session.get(IncidentReport, report_id.upper())
    if row is None:
        raise HTTPException(404, "Report not found")
    row.status = update.status
    row.updated_at = datetime.now(timezone.utc)
    db_session.commit()
    db_session.refresh(row)
    return report_out(row)
