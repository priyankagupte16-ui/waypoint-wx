from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now():
    return datetime.now(timezone.utc)


class PlaceCache(Base):
    __tablename__ = "place_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_key: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    payload: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Lookup(Base):
    __tablename__ = "lookups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_text: Mapped[str] = mapped_column(String(240))
    resolved_name: Mapped[str] = mapped_column(String(240), index=True)
    place_kind: Mapped[str] = mapped_column(String(40), default="city")
    country: Mapped[str] = mapped_column(String(80), default="")
    country_code: Mapped[str] = mapped_column(String(8), default="")
    admin1: Mapped[str] = mapped_column(String(120), default="")
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    units: Mapped[str] = mapped_column(String(16), default="celsius")
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(240), default="")
    source: Mapped[str] = mapped_column(String(24), default="mixed")
    timezone: Mapped[str] = mapped_column(String(64), default="")
    avg_temp_c: Mapped[float] = mapped_column(Float, default=0)
    min_temp_c: Mapped[float] = mapped_column(Float, default=0)
    max_temp_c: Mapped[float] = mapped_column(Float, default=0)
    rain_days: Mapped[int] = mapped_column(Integer, default=0)
    extras_json: Mapped[str] = mapped_column(Text, default="{}")
    insights_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    days = relationship(
        "DailyReading",
        back_populates="lookup",
        cascade="all, delete-orphan",
        order_by="DailyReading.day",
    )


class DailyReading(Base):
    __tablename__ = "daily_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lookup_id: Mapped[int] = mapped_column(ForeignKey("lookups.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    tmin_c: Mapped[float] = mapped_column(Float)
    tmax_c: Mapped[float] = mapped_column(Float)
    tmean_c: Mapped[float] = mapped_column(Float)
    precip_mm: Mapped[float] = mapped_column(Float, default=0)
    weather_code: Mapped[int] = mapped_column(Integer, default=0)
    wind_max: Mapped[float] = mapped_column(Float, default=0)
    sunrise: Mapped[str] = mapped_column(String(40), default="")
    sunset: Mapped[str] = mapped_column(String(40), default="")

    lookup = relationship("Lookup", back_populates="days")
