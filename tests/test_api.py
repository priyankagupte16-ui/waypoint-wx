from unittest.mock import patch

from app.db import Base, engine
from tests.conftest import api

PLACE = {
    "query": "Paris",
    "name": "Paris",
    "display": "Paris, Ile-de-France, France",
    "kind": "city",
    "country": "France",
    "country_code": "FR",
    "admin1": "Ile-de-France",
    "latitude": 48.8566,
    "longitude": 2.3522,
    "score": 0.99,
    "population": 2_000_000,
}

WX = {
    "timezone": "Europe/Paris",
    "source": "archive",
    "days": [
        {
            "day": "2024-06-01",
            "tmin_c": 14.0,
            "tmax_c": 22.0,
            "tmean_c": 18.0,
            "precip_mm": 0.2,
            "weather_code": 1,
            "condition": "Mostly clear",
            "wind_max": 12.0,
            "sunrise": "2024-06-01T05:50",
            "sunset": "2024-06-01T21:40",
        },
        {
            "day": "2024-06-02",
            "tmin_c": 15.0,
            "tmax_c": 24.0,
            "tmean_c": 19.2,
            "precip_mm": 4.0,
            "weather_code": 61,
            "condition": "Light rain",
            "wind_max": 18.0,
            "sunrise": "2024-06-02T05:49",
            "sunset": "2024-06-02T21:41",
        },
    ],
    "avg_temp_c": 18.6,
    "min_temp_c": 14.0,
    "max_temp_c": 24.0,
    "rain_days": 1,
}

EXTRAS = {
    "maps": {"google_maps": "https://www.google.com/maps/search/?api=1&query=48.85,2.35"},
    "youtube": {"search_url": "https://www.youtube.com/results?search_query=Paris+travel", "videos": []},
    "wikipedia": {"title": "Paris", "extract": "Capital of France"},
    "country": {"name": "France", "currencies": [{"code": "EUR"}]},
    "holidays": [],
    "air": {"us_aqi": 42, "band": "good"},
}


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_home():
    r = api().get("/")
    assert r.status_code == 200
    assert r.json()["assessment"].startswith("Tech Assessment")
    assert "PM Accelerator" in r.json()["company"]["name"]


def test_bad_dates():
    r = api().post(
        "/lookups",
        json={"location": "Paris", "start_date": "2024-06-10", "end_date": "2024-06-01"},
    )
    assert r.status_code == 422


@patch("app.store.gather", return_value=EXTRAS)
@patch("app.store.range_weather", return_value=WX)
@patch("app.store.pick_place", return_value=(PLACE, [PLACE]))
def test_crud_and_export(_p, _w, _g):
    c = api()
    created = c.post(
        "/lookups",
        json={
            "location": "Paris",
            "start_date": "2024-06-01",
            "end_date": "2024-06-02",
            "notes": "weekend trip",
            "tags": "france,trip",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    lid = body["id"]
    assert body["location"]["name"].startswith("Paris")
    assert len(body["days"]) == 2
    assert body["extras"]["youtube"]["search_url"]

    listed = c.get("/lookups?q=Paris")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    one = c.get(f"/lookups/{lid}")
    assert one.status_code == 200
    assert one.json()["notes"] == "weekend trip"

    patched = c.patch(f"/lookups/{lid}", json={"notes": "packed already"})
    assert patched.status_code == 200
    assert patched.json()["notes"] == "packed already"
    assert len(patched.json()["days"]) == 2

    for fmt in ("json", "csv", "xml", "md", "pdf"):
        exp = c.get(f"/lookups/{lid}/export", params={"format": fmt})
        assert exp.status_code == 200, fmt
        assert len(exp.content) > 10

    gone = c.delete(f"/lookups/{lid}")
    assert gone.status_code == 200
    missing = c.get(f"/lookups/{lid}")
    assert missing.status_code == 404
