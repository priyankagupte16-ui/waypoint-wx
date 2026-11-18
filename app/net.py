import httpx

from app.errors import AppError

UA = "WaypointWx/0.4 (assessment project; https://github.com)"
client = httpx.Client(
    timeout=httpx.Timeout(22.0, connect=8.0),
    headers={"User-Agent": UA},
    follow_redirects=True,
)


def get_json(url: str, params=None, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    try:
        r = client.get(url, params=params, headers=h)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        if not r.content:
            return None
        return r.json()
    except httpx.TimeoutException:
        host = url.split("/")[2] if "://" in url else url
        raise AppError(504, f"{host} timed out")
    except httpx.HTTPError:
        host = url.split("/")[2] if "://" in url else url
        raise AppError(502, f"could not reach {host}")
