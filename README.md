# Waypoint Wx

Backend for the PM Accelerator AI Engineer Intern assessment (Tech Assessment #2).

I built this as a small weather research API: you give it a place and a date range, it checks that the place is real, pulls daily temperatures, stores the whole thing, and lets you read / tweak / delete / export it later. Current conditions work too, without writing a row.

Author: **Priya**

## Product Manager Accelerator

This project was built for [Product Manager Accelerator](https://www.linkedin.com/school/pmaccelerator/). PMA is a product-management career program (PMA Pro, AI PM Bootcamp, leadership and resume support) that helps people break into PM and grow into senior roles. More on the company site: [pmaccelerator.io](https://www.pmaccelerator.io/).

## What it does

- Resolve a location from city, town, landmark, zip/postal code, or `lat,lon`
- Fuzzy match when the name is messy; if two countries both fit, the API asks you to pick
- Validate date ranges (order, length, not before 1940, not too far into the forecast window)
- CREATE a lookup: location + date range → daily temps persisted in SQLite
- READ one record or search previous lookups
- UPDATE notes/tags/units in place; changing location or dates re-fetches and re-validates
- DELETE a stored lookup
- Current weather for a place you have not saved yet
- Side data: OpenStreetMap + Google Maps links, YouTube search (real video list if you add an API key), Wikipedia, country/currency/driving side, public holidays in range, air quality
- Travel-ish notes: pack list, heat/freeze/rain flags, best-looking day in the range
- Export a record or the whole table as JSON, XML, CSV, Markdown, or PDF

Weather and geocoding use Open-Meteo, Photon, and Nominatim so the project runs without paid keys. Optional keys (YouTube, Google Static Maps) sit in `.env` if you have them.

## Setup

Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive API. http://127.0.0.1:8000/ is a short about page (name + PMA blurb).

```bash
pytest
```

## Useful calls

```bash
# fuzzy place search
curl "http://127.0.0.1:8000/places?q=eiffel%20tower"

# current conditions (zip)
curl "http://127.0.0.1:8000/weather/now?location=10001"

# store a range (historical or mixed with forecast)
curl -X POST http://127.0.0.1:8000/lookups -H "Content-Type: application/json" -d "{\"location\":\"Lisbon\",\"start_date\":\"2024-05-01\",\"end_date\":\"2024-05-05\",\"notes\":\"weekend\",\"tags\":\"pt\"}"

curl http://127.0.0.1:8000/lookups
curl http://127.0.0.1:8000/lookups/1
curl -X PATCH http://127.0.0.1:8000/lookups/1 -H "Content-Type: application/json" -d "{\"notes\":\"changed plans\"}"
curl http://127.0.0.1:8000/lookups/1/export?format=csv --output lisbon.csv
curl -X DELETE http://127.0.0.1:8000/lookups/1
```

If a name is ambiguous you get HTTP 409 plus a `candidates` list. Send the same body with `"pick_first": true` or a more specific query (`Springfield, IL`).

## Layout

```
app/          API, models, weather/geo helpers
tests/        date rules + mocked CRUD/export
requirements.txt
```

SQLite file is `waypoint.db` in the project root (created on first boot). Schema is `lookups` + `daily_readings` + a small geocode cache.

## Demo video

Add your walkthrough URL here before submitting the Google form.
