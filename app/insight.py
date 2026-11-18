from app.wmo import label


def _pack(avg, rainy, windy, snow):
    bag = []
    if avg < 5:
        bag += ["insulated jacket", "warm layers", "gloves"]
    elif avg < 15:
        bag += ["light jacket", "long sleeves"]
    elif avg < 24:
        bag += ["light layers", "comfortable walking shoes"]
    else:
        bag += ["breathable clothes", "sun hat", "refillable bottle"]
    if rainy:
        bag += ["compact umbrella", "water-resistant shoes"]
    if windy:
        bag.append("windbreaker")
    if snow:
        bag += ["boots with grip", "extra socks"]
    seen = []
    for item in bag:
        if item not in seen:
            seen.append(item)
    return seen


def build(days: list, extras: dict, place: dict):
    if not days:
        return {}
    avg = sum(d["tmean_c"] for d in days) / len(days)
    rain_days = [d for d in days if d["precip_mm"] >= 1]
    hot = max(days, key=lambda d: d["tmax_c"])
    cold = min(days, key=lambda d: d["tmin_c"])
    wettest = max(days, key=lambda d: d["precip_mm"])
    windy = any(d["wind_max"] >= 40 for d in days)
    snow = any(d["weather_code"] in {71, 73, 75, 77, 85, 86} for d in days)
    flags = []
    if hot["tmax_c"] >= 32:
        flags.append("heat: plan shade and extra water on " + hot["day"])
    if cold["tmin_c"] <= 0:
        flags.append("freeze risk overnight on " + cold["day"])
    if wettest["precip_mm"] >= 10:
        flags.append("soaking rain likely on " + wettest["day"])
    if windy:
        flags.append("gusty days in this stretch — outdoor plans may slip")
    air = extras.get("air") or {}
    aqi = air.get("us_aqi")
    if aqi and aqi >= 101:
        flags.append("air quality is rough (" + str(air.get("band")) + ") — cut outdoor cardio")
    holidays = extras.get("holidays") or []
    if holidays:
        flags.append("public holiday(s) in range: " + ", ".join(h["name"] for h in holidays[:3]))

    best = min(days, key=lambda d: (d["precip_mm"] * 4) + abs(d["tmean_c"] - 21) + (2 if d["weather_code"] >= 61 else 0))
    currencies = (extras.get("country") or {}).get("currencies") or []
    currency = currencies[0].get("code") if currencies else None
    drive = (extras.get("country") or {}).get("drive_side")

    notes = [
        f"{place.get('display') or place.get('name')} averages {avg:.1f}C across the range.",
        f"Best looking day is {best['day']} ({label(best['weather_code'])}, {best['tmean_c']}C).",
    ]
    if currency:
        notes.append(f"Local currency is {currency}.")
    if drive:
        notes.append(f"Traffic keeps to the {drive} side of the road.")

    return {
        "headline": notes[0],
        "best_day": best["day"],
        "pack": _pack(avg, bool(rain_days), windy, snow),
        "flags": flags,
        "notes": notes,
        "rain_day_count": len(rain_days),
    }
