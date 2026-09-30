"""Data model: transformers, customers, daily transformer readings, monthly billing,
and anonymous community incident reports.

Customers and reporters carry no personal details. All analysis is done at transformer
level (POPIA).
"""

from datetime import date, datetime
from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Transformer(Base):
    __tablename__ = "transformers"
    __table_args__ = (
        CheckConstraint("capacity_kva > 0", name="capacity_positive"),
        CheckConstraint("lat BETWEEN -90 AND 90 AND lon BETWEEN -180 AND 180", name="valid_coords"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    ward: Mapped[str | None] = mapped_column(String(32), index=True)
    lat: Mapped[float] = mapped_column(Numeric(9, 6, asdecimal=False), nullable=False)
    lon: Mapped[float] = mapped_column(Numeric(9, 6, asdecimal=False), nullable=False)
    capacity_kva: Mapped[Decimal] = mapped_column(Numeric(8, 1), nullable=False)
    # Derived from lat/lon so spatial queries (nearest neighbours) can use a GiST index.
    geom = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        Computed(
            "ST_SetSRID(ST_MakePoint(lon::float8, lat::float8), 4326)::geography",
            persisted=True,
        ),
    )

    customers: Mapped[list["Customer"]] = relationship(back_populates="transformer")
    readings: Mapped[list["TransformerReading"]] = relationship(back_populates="transformer")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("meter_type IN ('prepaid', 'conventional')", name="valid_meter_type"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    transformer_id: Mapped[str] = mapped_column(
        ForeignKey("transformers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Registered as indigent: eligible for Free Basic Electricity.
    is_indigent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    meter_type: Mapped[str] = mapped_column(String(16), nullable=False, default="prepaid")

    transformer: Mapped[Transformer] = relationship(back_populates="customers")
    bills: Mapped[list["Billing"]] = relationship(back_populates="customer")


class TransformerReading(Base):
    """Energy supplied by a transformer on one day (from its bulk meter)."""

    __tablename__ = "transformer_readings"
    __table_args__ = (
        CheckConstraint("energy_kwh >= 0", name="energy_non_negative"),
        CheckConstraint("peak_kva IS NULL OR peak_kva >= 0", name="peak_non_negative"),
    )

    transformer_id: Mapped[str] = mapped_column(
        ForeignKey("transformers.id", ondelete="CASCADE"), primary_key=True
    )
    reading_date: Mapped[date] = mapped_column(Date, primary_key=True)
    energy_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Highest demand that day; utilisation = peak_kva / capacity_kva.
    peak_kva: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    # Daily mean air temperature, a feature for the overload forecast.
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))

    transformer: Mapped[Transformer] = relationship(back_populates="readings")


class Billing(Base):
    """kWh billed (or prepaid-vended) to a customer in one month."""

    __tablename__ = "billing"
    __table_args__ = (
        CheckConstraint("kwh_billed >= 0", name="billed_non_negative"),
        CheckConstraint("EXTRACT(DAY FROM billing_month) = 1", name="month_starts_on_first"),
    )

    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True
    )
    # First day of the billing month, e.g. 2026-07-01.
    billing_month: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    kwh_billed: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="bills")


REPORT_CATEGORIES = ("outage", "cable_theft", "exposed_wiring", "tampering", "sparking")
REPORT_STATUSES = ("new", "dispatched", "resolved")


class IncidentReport(Base):
    """A fault or crime reported by a resident. Anonymous: no name, phone or address."""

    __tablename__ = "incident_reports"
    __table_args__ = (
        CheckConstraint(
            "category IN (" + ", ".join(f"'{c}'" for c in REPORT_CATEGORIES) + ")",
            name="valid_report_category",
        ),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in REPORT_STATUSES) + ")",
            name="valid_report_status",
        ),
    )

    # Short reference code shown to the resident, e.g. "K7Q2MX".
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    lat: Mapped[float] = mapped_column(Numeric(9, 6, asdecimal=False), nullable=False)
    lon: Mapped[float] = mapped_column(Numeric(9, 6, asdecimal=False), nullable=False)
    # Nearest transformer within 1 km, so reports show up on its detail panel.
    transformer_id: Mapped[str | None] = mapped_column(
        ForeignKey("transformers.id", ondelete="SET NULL"), index=True
    )
    is_urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
