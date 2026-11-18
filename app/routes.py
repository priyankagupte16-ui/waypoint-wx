from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.dates import check_range
from app.db import get_db
from app.errors import AppError
from app.exportkit import EXPORTERS
from app.extras import gather
from app.geo import pick_place, search_places
from app.insight import build
from app.models import Lookup
from app.present import lookup_out
from app.schemas import LookupIn, LookupPatch
from app.settings import settings
from app.store import create_lookup, delete_lookup, get_one, list_lookups, patch_lookup
from app.units import to_out, unit_labels
from app.wx import current_weather

router = APIRouter()

ABOUT = {
    "app": settings.app_name,
    "author": settings.author_name,
    "assessment": "Tech Assessment #2 (backend)",
    "company": {
        "name": "Product Manager Accelerator (PM Accelerator)",
        "linkedin": "https://www.linkedin.com/school/pmaccelerator/",
        "site": "https://www.pmaccelerator.io/",
        "blurb": (
            "The Product Manager Accelerator Program supports PM professionals through "
            "every stage of their careers, from students looking for entry-level roles "
            "to directors moving into leadership. PMA offers PMA Pro, an AI PM Bootcamp, "
            "power-skills training, leadership coaching, and resume support. The community "
            "is built around hands-on product work and helping people land and grow in "
            "product management roles."
        ),
    },
}


@router.get("/")
def home():
    return {
        **ABOUT,
        "docs": "/docs",
        "health": "/health",
        "hints": {
            "resolve": "GET /places?q=eiffel+tower",
            "now": "GET /weather/now?location=10001",
            "create": "POST /lookups",
            "export": "GET /lookups/{id}/export?format=csv",
        },
    }


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/about")
def about():
    return ABOUT


@router.get("/places")
def places(q: str = Query(min_length=2), db: Session = Depends(get_db)):
    return {"query": q, "matches": search_places(q, db)[:8]}


@router.get("/weather/now")
def weather_now(
    location: str = Query(min_length=2),
    units: str = "celsius",
    pick_first: bool = False,
    db: Session = Depends(get_db),
):
    units = units.lower()
    if units not in {"celsius", "fahrenheit"}:
        raise AppError(422, "units must be celsius or fahrenheit")
    place, alts = pick_place(location, db, force_first=pick_first)
    wx = current_weather(place["latitude"], place["longitude"])
    extras = gather(place, wx_date_today(), wx_date_today())
    tips = build(
        [
            {
                "day": wx.get("observed_at") or "",
                "tmin_c": wx.get("temperature_c") or 0,
                "tmax_c": wx.get("temperature_c") or 0,
                "tmean_c": wx.get("temperature_c") or 0,
                "precip_mm": wx.get("precip_mm") or 0,
                "weather_code": wx.get("weather_code") or 0,
                "wind_max": wx.get("wind_kmh") or 0,
            }
        ],
        extras,
        place,
    )
    labels = unit_labels(units)
    return {
        "location": place,
        "also_matched": alts[1:5],
        "units": units,
        "now": {
            **wx,
            "temperature": to_out(wx.get("temperature_c"), units),
            "feels_like": to_out(wx.get("feels_like_c"), units),
            "unit": labels["temp"],
        },
        "extras": extras,
        "insights": tips,
    }


def wx_date_today():
    from datetime import date

    return date.today()


@router.post("/lookups", status_code=201)
def create(payload: LookupIn, db: Session = Depends(get_db)):
    check_range(payload.start_date, payload.end_date)
    row = create_lookup(db, payload)
    return lookup_out(row)


@router.get("/lookups")
def list_all(
    q: str | None = None,
    country: str | None = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
):
    total, rows = list_lookups(db, q=q, country=country, page=page, size=size)
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [lookup_out(r, include_days=False) for r in rows],
    }


@router.get("/lookups/{lookup_id}")
def read_one(lookup_id: int, db: Session = Depends(get_db)):
    return lookup_out(get_one(db, lookup_id))


@router.patch("/lookups/{lookup_id}")
def update_one(lookup_id: int, payload: LookupPatch, db: Session = Depends(get_db)):
    if payload.start_date or payload.end_date:
        row = get_one(db, lookup_id)
        start = payload.start_date or row.start_date
        end = payload.end_date or row.end_date
        check_range(start, end)
    return lookup_out(patch_lookup(db, lookup_id, payload))


@router.delete("/lookups/{lookup_id}")
def remove_one(lookup_id: int, db: Session = Depends(get_db)):
    return delete_lookup(db, lookup_id)


@router.post("/lookups/compare")
def compare(
    a: str = Query(min_length=2),
    b: str = Query(min_length=2),
    units: str = "celsius",
    db: Session = Depends(get_db),
):
    left, _ = pick_place(a, db, force_first=True)
    right, _ = pick_place(b, db, force_first=True)
    wa = current_weather(left["latitude"], left["longitude"])
    wb = current_weather(right["latitude"], right["longitude"])
    ta = to_out(wa.get("temperature_c"), units)
    tb = to_out(wb.get("temperature_c"), units)
    delta = None
    if ta is not None and tb is not None:
        delta = round(ta - tb, 1)
    return {
        "units": units,
        "a": {"location": left, "now": wa, "temperature": ta},
        "b": {"location": right, "now": wb, "temperature": tb},
        "delta_a_minus_b": delta,
        "warmer": left["display"] if (delta or 0) > 0 else right["display"] if delta else None,
    }


@router.get("/lookups/{lookup_id}/export")
def export_one(lookup_id: int, format: str = "json", db: Session = Depends(get_db)):
    fmt = format.lower().strip()
    if fmt not in EXPORTERS:
        raise AppError(422, "format must be json, csv, xml, md, or pdf")
    mime, ext, fn = EXPORTERS[fmt]
    row = get_one(db, lookup_id)
    blob = fn([row])
    name = f"lookup-{lookup_id}{ext}"
    return Response(
        content=blob,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/export")
def export_all(format: str = "json", db: Session = Depends(get_db)):
    fmt = format.lower().strip()
    if fmt not in EXPORTERS:
        raise AppError(422, "format must be json, csv, xml, md, or pdf")
    mime, ext, fn = EXPORTERS[fmt]
    rows = db.query(Lookup).order_by(Lookup.id.asc()).all()
    blob = fn(rows)
    return Response(
        content=blob,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="lookups{ext}"'},
    )
