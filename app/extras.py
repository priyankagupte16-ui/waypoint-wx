from datetime import date
from urllib.parse import quote_plus

from app.net import get_json
from app.settings import settings


def _yt_search_url(place: str) -> str:
    return "https://www.youtube.com/results?search_query=" + quote_plus(place + " travel")


def youtube_bits(place: dict):
    q = place.get("display") or place.get("name")
    out = {"search_url": _yt_search_url(q), "videos": []}
    key = (settings.youtube_api_key or "").strip()
    if not key:
        return out
    data = get_json(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "part": "snippet",
            "q": f"{q} travel weather",
            "type": "video",
            "maxResults": 5,
            "key": key,
        },
    )
    if not data:
        return out
    for item in data.get("items") or []:
        vid = (item.get("id") or {}).get("videoId")
        sn = item.get("snippet") or {}
        if not vid:
            continue
        out["videos"].append(
            {
                "id": vid,
                "title": sn.get("title"),
                "channel": sn.get("channelTitle"),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "thumb": (sn.get("thumbnails") or {}).get("medium", {}).get("url"),
            }
        )
    return out


def maps_bits(place: dict):
    lat, lon = place["latitude"], place["longitude"]
    pad = 0.08
    bbox = f"{lon - pad},{lat - pad},{lon + pad},{lat + pad}"
    gmaps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    static = None
    key = (settings.google_maps_api_key or "").strip()
    if key:
        static = (
            "https://maps.googleapis.com/maps/api/staticmap"
            f"?center={lat},{lon}&zoom=11&size=640x360&markers={lat},{lon}&key={key}"
        )
    return {
        "latitude": lat,
        "longitude": lon,
        "google_maps": gmaps,
        "google_static": static,
        "osm_page": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=12/{lat}/{lon}",
        "osm_embed": f"https://www.openstreetmap.org/export/embed.html?bbox={bbox}&layer=mapnik&marker={lat},{lon}",
    }


def wiki_bits(place: dict):
    title = place.get("name") or ""
    data = get_json(
        "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote_plus(title.replace(" ", "_"))
    )
    if not data or data.get("type") == "disambiguation" or data.get("title") == "Not found":
        loc = ", ".join(x for x in [place.get("name"), place.get("admin1"), place.get("country")] if x)
        data = get_json(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote_plus(loc.replace(" ", "_"))
        )
    if not data:
        return {}
    thumb = (data.get("thumbnail") or {}).get("source")
    return {
        "title": data.get("title"),
        "extract": data.get("extract"),
        "url": (data.get("content_urls") or {}).get("desktop", {}).get("page"),
        "thumbnail": thumb,
    }


def country_bits(code: str):
    if not code:
        return {}
    data = get_json(f"https://restcountries.com/v3.1/alpha/{code}")
    if not data:
        return {}
    row = data[0] if isinstance(data, list) else data
    currencies = row.get("currencies") or {}
    money = []
    for k, v in currencies.items():
        money.append({"code": k, "name": v.get("name"), "symbol": v.get("symbol")})
    langs = list((row.get("languages") or {}).values())
    idd = row.get("idd") or {}
    root = idd.get("root") or ""
    suf = (idd.get("suffixes") or [""])[0]
    return {
        "name": (row.get("name") or {}).get("common"),
        "capital": (row.get("capital") or [None])[0],
        "region": row.get("region"),
        "currencies": money,
        "languages": langs,
        "calling_code": f"{root}{suf}" if root else "",
        "flag": (row.get("flags") or {}).get("png"),
        "drive_side": (row.get("car") or {}).get("side"),
    }


def holidays_bits(code: str, start: date, end: date):
    if not code:
        return []
    years = {start.year, end.year}
    found = []
    for y in sorted(years):
        data = get_json(f"https://date.nager.at/api/v3/PublicHolidays/{y}/{code}")
        if not data:
            continue
        for h in data:
            d = h.get("date")
            if not d:
                continue
            try:
                hd = date.fromisoformat(d)
            except ValueError:
                continue
            if start <= hd <= end:
                found.append({"date": d, "name": h.get("localName") or h.get("name"), "global": h.get("global")})
    return found


def air_bits(lat: float, lon: float):
    data = get_json(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "us_aqi,european_aqi,pm2_5,pm10,ozone,uv_index",
        },
    )
    if not data or "current" not in data:
        return {}
    cur = data["current"]
    aqi = cur.get("us_aqi")
    band = "unknown"
    if aqi is not None:
        if aqi <= 50:
            band = "good"
        elif aqi <= 100:
            band = "moderate"
        elif aqi <= 150:
            band = "unhealthy for sensitive groups"
        elif aqi <= 200:
            band = "unhealthy"
        else:
            band = "very unhealthy"
    return {
        "us_aqi": aqi,
        "band": band,
        "pm2_5": cur.get("pm2_5"),
        "pm10": cur.get("pm10"),
        "ozone": cur.get("ozone"),
        "uv_index": cur.get("uv_index"),
    }


def gather(place: dict, start: date, end: date):
    extras = {"maps": maps_bits(place), "youtube": {"search_url": _yt_search_url(place.get("display") or place.get("name")), "videos": []}}
    try:
        extras["youtube"] = youtube_bits(place)
    except Exception:
        pass
    try:
        extras["wikipedia"] = wiki_bits(place)
    except Exception:
        extras["wikipedia"] = {}
    try:
        extras["country"] = country_bits(place.get("country_code") or "")
    except Exception:
        extras["country"] = {}
    try:
        extras["holidays"] = holidays_bits(place.get("country_code") or "", start, end)
    except Exception:
        extras["holidays"] = []
    try:
        extras["air"] = air_bits(place["latitude"], place["longitude"])
    except Exception:
        extras["air"] = {}
    return extras
