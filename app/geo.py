import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import PlaceCache
from app.net import get_json

COORD_RE = re.compile(
    r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$"
)
ZIPISH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{2,11}$")


def _key(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def _fresh(row: PlaceCache) -> bool:
    age = datetime.now(timezone.utc) - row.fetched_at.replace(tzinfo=timezone.utc)
    return age < timedelta(days=10)


def _pack(item: dict, score: float, kind: str, raw_query: str):
    return {
        "query": raw_query,
        "name": item.get("name") or item.get("display") or raw_query,
        "display": item.get("display") or item.get("name") or raw_query,
        "kind": kind,
        "country": item.get("country") or "",
        "country_code": (item.get("country_code") or "").upper(),
        "admin1": item.get("admin1") or "",
        "latitude": float(item["latitude"]),
        "longitude": float(item["longitude"]),
        "score": round(score, 3),
        "population": item.get("population") or 0,
    }


def _from_open_meteo(q: str):
    data = get_json(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": q, "count": 8, "language": "en", "format": "json"},
    )
    out = []
    if not data or not data.get("results"):
        return out
    for row in data["results"]:
        pop = row.get("population") or 0
        score = 0.55
        if pop:
            score += min(0.35, pop / 8_000_000)
        name = row.get("name") or ""
        if name.lower() == q.lower():
            score += 0.12
        bits = [name, row.get("admin1"), row.get("country")]
        display = ", ".join(x for x in bits if x)
        out.append(
            _pack(
                {
                    "name": name,
                    "display": display,
                    "country": row.get("country") or "",
                    "country_code": row.get("country_code") or "",
                    "admin1": row.get("admin1") or "",
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "population": pop,
                },
                score,
                "city",
                q,
            )
        )
    return out


def _from_photon(q: str):
    data = get_json("https://photon.komoot.io/api/", params={"q": q, "limit": 6})
    out = []
    if not data or not data.get("features"):
        return out
    for feat in data["features"]:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]
        name = props.get("name") or q
        osm_value = props.get("osm_value") or props.get("type") or "place"
        kind = "landmark" if osm_value in {
            "attraction",
            "museum",
            "monument",
            "peak",
            "park",
            "airport",
            "station",
            "university",
            "castle",
            "viewpoint",
            "tower",
            "artwork",
        } else "place"
        city = props.get("city") or props.get("town") or ""
        country = props.get("country") or ""
        display = ", ".join(x for x in [name, city, props.get("state"), country] if x)
        score = 0.32
        if props.get("osm_key") == "tourism":
            score += 0.18
        if kind == "landmark":
            score += 0.08
        if city:
            score += 0.05
        if name.lower() == q.lower():
            score += 0.2
        elif name.lower() in q.lower() or q.lower() in name.lower():
            score += 0.1
        out.append(
            _pack(
                {
                    "name": name,
                    "display": display,
                    "country": country,
                    "country_code": props.get("countrycode") or "",
                    "admin1": props.get("state") or city,
                    "latitude": lat,
                    "longitude": lon,
                },
                score,
                kind,
                q,
            )
        )
    return out


def _from_nominatim(q: str):
    data = get_json(
        "https://nominatim.openstreetmap.org/search",
        params={"q": q, "format": "jsonv2", "limit": 5, "addressdetails": 1},
    )
    out = []
    if not data:
        return out
    for row in data:
        addr = row.get("address") or {}
        name = row.get("name") or row.get("display_name", "").split(",")[0]
        kind = "zip" if addr.get("postcode") and q.replace(" ", "")[:5] in str(addr.get("postcode", "")) else "place"
        if row.get("type") in {"attraction", "tourism", "museum"}:
            kind = "landmark"
        score = 0.4 + float(row.get("importance") or 0.25)
        if kind == "landmark":
            score += 0.08
        out.append(
            _pack(
                {
                    "name": name,
                    "display": row.get("display_name") or name,
                    "country": addr.get("country") or "",
                    "country_code": addr.get("country_code") or "",
                    "admin1": addr.get("state") or addr.get("county") or "",
                    "latitude": row["lat"],
                    "longitude": row["lon"],
                },
                score,
                kind,
                q,
            )
        )
    return out


def reverse_point(lat: float, lon: float, raw_query: str):
    data = get_json(
        "https://nominatim.openstreetmap.org/reverse",
        params={"lat": lat, "lon": lon, "format": "jsonv2"},
    )
    if not data:
        return _pack(
            {
                "name": f"{lat:.4f},{lon:.4f}",
                "display": f"{lat:.4f}, {lon:.4f}",
                "latitude": lat,
                "longitude": lon,
            },
            1.0,
            "coords",
            raw_query,
        )
    addr = data.get("address") or {}
    name = data.get("name") or addr.get("city") or addr.get("town") or addr.get("village") or "Dropped pin"
    return _pack(
        {
            "name": name,
            "display": data.get("display_name") or name,
            "country": addr.get("country") or "",
            "country_code": addr.get("country_code") or "",
            "admin1": addr.get("state") or "",
            "latitude": lat,
            "longitude": lon,
        },
        1.0,
        "coords",
        raw_query,
    )


def _merge(buckets):
    seen = {}
    for hit in buckets:
        k = (round(hit["latitude"], 3), round(hit["longitude"], 3))
        if k not in seen or hit["score"] > seen[k]["score"]:
            seen[k] = hit
    ranked = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
    return ranked


def search_places(q: str, db: Session | None = None):
    q = (q or "").strip()
    if len(q) < 2:
        raise AppError(422, "location is too short")

    m = COORD_RE.match(q)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise AppError(422, "coordinates are out of range")
        return [reverse_point(lat, lon, q)]

    cache_key = _key(q)
    if db is not None:
        row = db.query(PlaceCache).filter(PlaceCache.query_key == cache_key).first()
        if row and _fresh(row):
            return json.loads(row.payload)

    hits = []
    try:
        hits.extend(_from_open_meteo(q))
    except AppError:
        pass
    try:
        hits.extend(_from_photon(q))
    except AppError:
        pass
    if len(hits) < 2 or ZIPISH.match(q):
        try:
            hits.extend(_from_nominatim(q))
        except AppError:
            pass

    ranked = _merge(hits)
    if db is not None and ranked:
        blob = json.dumps(ranked[:8])
        existing = db.query(PlaceCache).filter(PlaceCache.query_key == cache_key).first()
        if existing:
            existing.payload = blob
            existing.fetched_at = datetime.now(timezone.utc)
        else:
            db.add(PlaceCache(query_key=cache_key, payload=blob))
        db.commit()
    return ranked


def pick_place(q: str, db: Session | None = None, force_first: bool = False):
    ranked = search_places(q, db)
    if not ranked:
        raise AppError(404, f"could not find a place matching '{q}'")
    if not force_first and len(ranked) > 1:
        gap = ranked[0]["score"] - ranked[1]["score"]
        same_country = ranked[0].get("country") == ranked[1].get("country")
        if gap < 0.06 and not same_country:
            raise AppError(
                409,
                "that name matches more than one place — pick one from candidates",
                {"candidates": ranked[:6]},
            )
    return ranked[0], ranked[:6]
