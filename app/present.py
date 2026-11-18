import json
from datetime import date, datetime

from app.models import DailyReading, Lookup
from app.units import mm_out, to_out, unit_labels
from app.wmo import label


def _iso(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v


def day_out(row: DailyReading, unit: str):
    return {
        "date": _iso(row.day),
        "tmin": to_out(row.tmin_c, unit),
        "tmax": to_out(row.tmax_c, unit),
        "tmean": to_out(row.tmean_c, unit),
        "precip": mm_out(row.precip_mm, unit),
        "weather_code": row.weather_code,
        "condition": label(row.weather_code),
        "wind_max_kmh": row.wind_max,
        "sunrise": row.sunrise,
        "sunset": row.sunset,
    }


def lookup_out(row: Lookup, include_days=True):
    unit = row.units or "celsius"
    labels = unit_labels(unit)
    try:
        extras = json.loads(row.extras_json or "{}")
    except json.JSONDecodeError:
        extras = {}
    try:
        insights = json.loads(row.insights_json or "{}")
    except json.JSONDecodeError:
        insights = {}
    body = {
        "id": row.id,
        "query": row.query_text,
        "location": {
            "name": row.resolved_name,
            "kind": row.place_kind,
            "country": row.country,
            "country_code": row.country_code,
            "admin1": row.admin1,
            "latitude": row.latitude,
            "longitude": row.longitude,
        },
        "start_date": _iso(row.start_date),
        "end_date": _iso(row.end_date),
        "units": unit,
        "unit_labels": labels,
        "notes": row.notes,
        "tags": [t.strip() for t in (row.tags or "").split(",") if t.strip()],
        "source": row.source,
        "timezone": row.timezone,
        "summary": {
            "avg": to_out(row.avg_temp_c, unit),
            "min": to_out(row.min_temp_c, unit),
            "max": to_out(row.max_temp_c, unit),
            "rain_days": row.rain_days,
        },
        "extras": extras,
        "insights": insights,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }
    if include_days:
        body["days"] = [day_out(d, unit) for d in row.days]
    return body
