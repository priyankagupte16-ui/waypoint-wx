from datetime import date

from app.dates import split_sources
from app.errors import AppError
from app.net import get_json
from app.wmo import label

DAILY = ",".join(
    [
        "temperature_2m_max",
        "temperature_2m_min",
        "temperature_2m_mean",
        "precipitation_sum",
        "weather_code",
        "wind_speed_10m_max",
        "sunrise",
        "sunset",
    ]
)

CURRENT = ",".join(
    [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "weather_code",
        "wind_speed_10m",
        "wind_gusts_10m",
        "precipitation",
        "cloud_cover",
        "pressure_msl",
        "is_day",
    ]
)


def _num(v, default=0.0):
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _rows_from(payload: dict):
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    rows = []
    for i, day in enumerate(times):
        tmax = _num((daily.get("temperature_2m_max") or [None])[i] if i < len(daily.get("temperature_2m_max") or []) else None)
        tmin = _num((daily.get("temperature_2m_min") or [None])[i] if i < len(daily.get("temperature_2m_min") or []) else None)
        means = daily.get("temperature_2m_mean") or []
        tmean = _num(means[i] if i < len(means) and means[i] is not None else None, (tmax + tmin) / 2)
        precip = daily.get("precipitation_sum") or []
        codes = daily.get("weather_code") or []
        winds = daily.get("wind_speed_10m_max") or []
        rise = daily.get("sunrise") or []
        sset = daily.get("sunset") or []
        code = int(codes[i]) if i < len(codes) and codes[i] is not None else 0
        rows.append(
            {
                "day": day,
                "tmin_c": round(tmin, 1),
                "tmax_c": round(tmax, 1),
                "tmean_c": round(tmean, 1),
                "precip_mm": round(_num(precip[i] if i < len(precip) else 0), 2),
                "weather_code": code,
                "condition": label(code),
                "wind_max": round(_num(winds[i] if i < len(winds) else 0), 1),
                "sunrise": rise[i] if i < len(rise) else "",
                "sunset": sset[i] if i < len(sset) else "",
            }
        )
    return rows, payload.get("timezone") or ""


def _fetch(url: str, lat: float, lon: float, start: date, end: date):
    data = get_json(
        url,
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": DAILY,
            "timezone": "auto",
        },
    )
    if not data or "daily" not in data:
        raise AppError(502, "weather provider returned an empty payload")
    return _rows_from(data)


def range_weather(lat: float, lon: float, start: date, end: date):
    hist, fc = split_sources(start, end)
    merged = []
    tz = ""
    sources = []
    if hist:
        rows, tz = _fetch(
            "https://archive-api.open-meteo.com/v1/archive",
            lat,
            lon,
            hist[0],
            hist[1],
        )
        merged.extend(rows)
        sources.append("archive")
    if fc:
        rows, tz2 = _fetch(
            "https://api.open-meteo.com/v1/forecast",
            lat,
            lon,
            fc[0],
            fc[1],
        )
        tz = tz or tz2
        merged.extend(rows)
        sources.append("forecast")

    by_day = {r["day"]: r for r in merged}
    ordered = [by_day[k] for k in sorted(by_day)]
    if not ordered:
        raise AppError(502, "no daily temperatures came back for that range")

    means = [r["tmean_c"] for r in ordered]
    mins = [r["tmin_c"] for r in ordered]
    maxs = [r["tmax_c"] for r in ordered]
    rain_days = sum(1 for r in ordered if r["precip_mm"] >= 1)
    return {
        "timezone": tz,
        "source": "mixed" if len(sources) > 1 else (sources[0] if sources else "unknown"),
        "days": ordered,
        "avg_temp_c": round(sum(means) / len(means), 1),
        "min_temp_c": round(min(mins), 1),
        "max_temp_c": round(max(maxs), 1),
        "rain_days": rain_days,
    }


def current_weather(lat: float, lon: float):
    data = get_json(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": CURRENT,
            "daily": "uv_index_max,precipitation_probability_max",
            "timezone": "auto",
        },
    )
    if not data or "current" not in data:
        raise AppError(502, "current conditions are unavailable right now")
    cur = data["current"]
    daily = data.get("daily") or {}
    code = int(cur.get("weather_code") or 0)
    uv = None
    if daily.get("uv_index_max"):
        uv = daily["uv_index_max"][0]
    pop = None
    if daily.get("precipitation_probability_max"):
        pop = daily["precipitation_probability_max"][0]
    return {
        "observed_at": cur.get("time"),
        "timezone": data.get("timezone"),
        "temperature_c": cur.get("temperature_2m"),
        "feels_like_c": cur.get("apparent_temperature"),
        "humidity": cur.get("relative_humidity_2m"),
        "wind_kmh": cur.get("wind_speed_10m"),
        "gusts_kmh": cur.get("wind_gusts_10m"),
        "precip_mm": cur.get("precipitation"),
        "cloud_cover": cur.get("cloud_cover"),
        "pressure_hpa": cur.get("pressure_msl"),
        "is_day": bool(cur.get("is_day")),
        "weather_code": code,
        "condition": label(code),
        "uv_index_max": uv,
        "precip_chance": pop,
    }
