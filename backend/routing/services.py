import math
from datetime import datetime, timedelta, timezone

import requests
from django.core.cache import cache

from .risk import checkpoint_risk

HEADERS = {"User-Agent": "weather-truck-routing-assessment/1.0"}
TRUCK_FACTOR = 1.15   # OSRM demo is a car profile; trucks are slower
HOURS = 49            # slider covers 0..48h after departure


def _get(url, params=None, ttl=900):
    key = url + repr(sorted((params or {}).items()))
    hit = cache.get(key)
    if hit is not None:
        return hit
    r = requests.get(url, params=params, headers=HEADERS, timeout=25)
    r.raise_for_status()
    data = r.json()
    cache.set(key, data, ttl)
    return data


def geocode(q):
    try:
        res = _get("https://nominatim.openstreetmap.org/search", {"q": q, "format": "json", "limit": 1}, 86400)
    except requests.RequestException:
        res = []  # Nominatim can block shared hosting IPs, so fall back to Open-Meteo geocoding
    if res:
        return [float(res[0]["lat"]), float(res[0]["lon"])]
    d = _get("https://geocoding-api.open-meteo.com/v1/search", {"name": q.split(",")[0].strip(), "count": 1}, 86400)
    if d.get("results"):
        return [d["results"][0]["latitude"], d["results"][0]["longitude"]]
    raise ValueError(f"Could not find location: {q}")


def get_routes(a, b):
    base = "https://router.project-osrm.org/route/v1/driving/"
    data = _get(base + f"{a[1]},{a[0]};{b[1]},{b[0]}", {"alternatives": 3, "overview": "full", "geometries": "geojson"})
    if data.get("code") != "Ok":
        raise ValueError("No drivable route found between those places")
    routes = data["routes"][:3]
    # OSRM often gives fewer than 3 alternatives: force one via a point off to the side of the straight line
    for sign in (1, -1):
        if len(routes) >= 3:
            break
        via = [(a[0] + b[0]) / 2 - sign * 0.2 * (b[1] - a[1]), (a[1] + b[1]) / 2 + sign * 0.2 * (b[0] - a[0])]
        d = _get(base + f"{a[1]},{a[0]};{via[1]},{via[0]};{b[1]},{b[0]}", {"overview": "full", "geometries": "geojson"})
        if d.get("code") == "Ok":
            r = d["routes"][0]
            if r["distance"] < 1.6 * routes[0]["distance"] and all(abs(r["distance"] - x["distance"]) > 0.03 * x["distance"] for x in routes):
                routes.append(r)
    return routes


def haversine(p, q):
    la1, lo1, la2, lo2 = map(math.radians, (*p, *q))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 3958.8 * math.asin(math.sqrt(h))


def sample(coords, step):
    cum = [0.0]
    for i in range(1, len(coords)):
        cum.append(cum[-1] + haversine(coords[i - 1], coords[i]))
    total = cum[-1]
    pts, j = [], 0
    for t in list(range(0, int(total), step)) + [total]:
        while j < len(cum) - 1 and cum[j] < t:
            j += 1
        pts.append((coords[j], cum[j]))
    return pts, total


def fetch_weather(points):
    out = []
    for i in range(0, len(points), 50):
        chunk = points[i:i + 50]
        d = _get("https://api.open-meteo.com/v1/forecast", {
            "latitude": ",".join(f"{p[0]:.3f}" for p in chunk),
            "longitude": ",".join(f"{p[1]:.3f}" for p in chunk),
            "hourly": "wind_speed_10m,rain,snowfall", "wind_speed_unit": "mph",
            "precipitation_unit": "inch", "timezone": "UTC", "forecast_days": 5})
        out += d if isinstance(d, list) else [d]
    return out


def build_route(route, rid, depart, load, step, demo=None):
    coords = [(c[1], c[0]) for c in route["geometry"]["coordinates"]]
    pts, total = sample(coords, step)
    duration_h = route["duration"] / 3600 * TRUCK_FACTOR
    wx = fetch_weather([p for p, _ in pts])
    t0 = datetime.fromisoformat(wx[0]["hourly"]["time"][0]).replace(tzinfo=timezone.utc)
    base = round((depart - t0).total_seconds() / 3600)
    cps = []
    for n, ((lat, lon), mile) in enumerate(pts):
        h = wx[n]["hourly"]

        def at(i):
            i = max(0, min(len(h["time"]) - 1, i))
            w, r, s = h["wind_speed_10m"][i] or 0, h["rain"][i] or 0, h["snowfall"][i] or 0
            if demo and rid == 0 and total and 0.3 <= mile / total <= 0.6:  # demo storm on Route A only
                w, r, s = max(w, demo.get("wind", 0)), max(r, demo.get("rain", 0)), max(s, demo.get("snow", 0))
            return w, r, s

        eta = depart + timedelta(hours=duration_h * mile / total if total else 0)
        wind, rain, snow = at(round((eta - t0).total_seconds() / 3600))
        cps.append({
            "lat": lat, "lon": lon, "mile": round(mile, 1), "eta": eta.isoformat(),
            "wind": round(wind, 1), "rain": round(rain, 2), "snow": round(snow, 2),
            "risk": checkpoint_risk(wind, rain, snow, load),
            "risk_by_hour": [checkpoint_risk(*at(base + k), load) for k in range(HOURS)],
            "seg": (pts[n + 1][1] - mile) if n + 1 < len(pts) else 0,
        })
    miles = lambda ok: round(sum(c["seg"] for c in cps if ok(c["risk"])), 1)
    skip = max(1, len(coords) // 500)
    return {
        "id": rid, "distance_mi": round(total, 1), "duration_h": round(duration_h, 2),
        "geometry": [list(c) for c in coords[::skip]] + [list(coords[-1])],
        "checkpoints": cps,
        "summary": {
            "severe_miles": miles(lambda r: r >= 3), "high_miles": miles(lambda r: r == 2),
            "avg_risk": round(sum(c["risk"] for c in cps) / len(cps), 2),
            "no_travel": any(c["risk"] == 4 for c in cps),
        },
    }


def recommend(routes):
    """No Travel routes are skipped; then severe miles > high miles > avg risk > time."""
    ok = [r for r in routes if not r["summary"]["no_travel"]] or routes
    s = lambda r: (r["summary"]["severe_miles"], r["summary"]["high_miles"], r["summary"]["avg_risk"], r["duration_h"])
    return min(ok, key=s)["id"]
