import json
from datetime import date, datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.dates import check_range
from app.errors import AppError
from app.extras import gather
from app.geo import pick_place
from app.insight import build
from app.models import DailyReading, Lookup
from app.wx import range_weather


def _fill_days(row: Lookup, days: list):
    row.days.clear()
    for d in days:
        row.days.append(
            DailyReading(
                day=date.fromisoformat(d["day"]) if isinstance(d["day"], str) else d["day"],
                tmin_c=d["tmin_c"],
                tmax_c=d["tmax_c"],
                tmean_c=d["tmean_c"],
                precip_mm=d["precip_mm"],
                weather_code=d["weather_code"],
                wind_max=d["wind_max"],
                sunrise=d.get("sunrise") or "",
                sunset=d.get("sunset") or "",
            )
        )


def hydrate(row: Lookup, place: dict, start: date, end: date, query_text: str):
    check_range(start, end)
    wx = range_weather(place["latitude"], place["longitude"], start, end)
    extras = gather(place, start, end)
    tips = build(wx["days"], extras, place)
    row.query_text = query_text
    row.resolved_name = place.get("display") or place.get("name")
    row.place_kind = place.get("kind") or "place"
    row.country = place.get("country") or ""
    row.country_code = place.get("country_code") or ""
    row.admin1 = place.get("admin1") or ""
    row.latitude = place["latitude"]
    row.longitude = place["longitude"]
    row.start_date = start
    row.end_date = end
    row.source = wx["source"]
    row.timezone = wx["timezone"]
    row.avg_temp_c = wx["avg_temp_c"]
    row.min_temp_c = wx["min_temp_c"]
    row.max_temp_c = wx["max_temp_c"]
    row.rain_days = wx["rain_days"]
    row.extras_json = json.dumps(extras)
    row.insights_json = json.dumps(tips)
    row.updated_at = datetime.now(timezone.utc)
    _fill_days(row, wx["days"])
    return row


def create_lookup(db: Session, payload):
    place, _ = pick_place(payload.location, db, force_first=payload.pick_first)
    row = Lookup(units=payload.units, notes=payload.notes or "", tags=payload.tags or "")
    hydrate(row, place, payload.start_date, payload.end_date, payload.location)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_one(db: Session, lookup_id: int) -> Lookup:
    row = db.get(Lookup, lookup_id)
    if not row:
        raise AppError(404, f"lookup {lookup_id} is not in the database")
    return row


def list_lookups(db: Session, q=None, country=None, page=1, size=20):
    page = max(1, page)
    size = min(100, max(1, size))
    stmt = db.query(Lookup)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.filter(
            or_(
                Lookup.resolved_name.ilike(like),
                Lookup.query_text.ilike(like),
                Lookup.notes.ilike(like),
            )
        )
    if country:
        stmt = stmt.filter(
            or_(Lookup.country.ilike(f"%{country}%"), Lookup.country_code.ilike(country))
        )
    total = stmt.count()
    rows = (
        stmt.order_by(Lookup.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return total, rows


def patch_lookup(db: Session, lookup_id: int, payload):
    row = get_one(db, lookup_id)
    refetch = False
    query_text = row.query_text
    place = {
        "name": row.resolved_name.split(",")[0],
        "display": row.resolved_name,
        "kind": row.place_kind,
        "country": row.country,
        "country_code": row.country_code,
        "admin1": row.admin1,
        "latitude": row.latitude,
        "longitude": row.longitude,
    }
    start, end = row.start_date, row.end_date

    if payload.notes is not None:
        row.notes = payload.notes
    if payload.tags is not None:
        row.tags = payload.tags
    if payload.units is not None:
        row.units = payload.units
    if payload.location:
        place, _ = pick_place(payload.location, db, force_first=payload.pick_first)
        query_text = payload.location
        refetch = True
    if payload.start_date or payload.end_date:
        start = payload.start_date or start
        end = payload.end_date or end
        refetch = True

    if refetch:
        hydrate(row, place, start, end, query_text)
    else:
        row.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(row)
    return row


def delete_lookup(db: Session, lookup_id: int):
    row = get_one(db, lookup_id)
    db.delete(row)
    db.commit()
    return {"deleted": lookup_id}
