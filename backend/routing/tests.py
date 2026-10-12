from django.test import SimpleTestCase

from .risk import RAIN, SNOW, band, checkpoint_risk, wind_level


class RiskTests(SimpleTestCase):
    def test_wind_bands(self):
        self.assertEqual([wind_level(w, 0) for w in (24.9, 25, 35, 45, 55)], [0, 1, 2, 3, 4])

    def test_rain_and_snow_bands(self):
        self.assertEqual([band(v, RAIN) for v in (0.09, 0.1, 0.25, 0.5, 1.0, 1.01)], [0, 1, 2, 3, 3, 4])
        self.assertEqual([band(v, SNOW) for v in (0.4, 0.5, 1.0, 2.0, 3.0, 3.01)], [0, 1, 2, 3, 3, 4])

    def test_load_rules(self):
        self.assertEqual(wind_level(56, 0), 4)
        self.assertEqual(wind_level(50, 30001), 4)
        self.assertEqual(wind_level(50, 30000), 3)
        self.assertEqual(wind_level(40, 40001), 3)
        self.assertEqual(wind_level(40, 40000), 2)

    def test_worst_condition_wins(self):
        self.assertEqual(checkpoint_risk(10, 0.3, 2.5, 20000), 3)


import json
import math
from datetime import datetime, timedelta
from unittest.mock import patch


def _line(off):
    return {"coordinates": [[-87.63 - 17.36 * t / 40, 41.88 - 2.14 * t / 40 + off * math.sin(math.pi * t / 40)] for t in range(41)]}


def fake_get(url, params=None, ttl=900):
    if "nominatim" in url:
        return [{"lat": "41.88", "lon": "-87.63"}] if "Chicago" in params["q"] else [{"lat": "39.74", "lon": "-104.99"}]
    if "osrm" in url:
        if url.count(";") == 1:
            return {"code": "Ok", "routes": [{"distance": 1.6e6, "duration": 72000, "geometry": _line(0)},
                                             {"distance": 1.75e6, "duration": 79000, "geometry": _line(1)}]}
        return {"code": "Ok", "routes": [{"distance": 1.95e6, "duration": 88000, "geometry": _line(2)}]}
    hours = [(datetime(2026, 10, 12) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(120)]
    one = {"hourly": {"time": hours, "wind_speed_10m": [10.0] * 120, "rain": [0.0] * 120, "snowfall": [0.0] * 120}}
    k = len(params["latitude"].split(","))
    return [one] * k if k > 1 else one


@patch("routing.services._get", side_effect=fake_get)
class PlanEndpointTests(SimpleTestCase):
    def post(self, load=40000, demo=None):
        body = {"origin": "Chicago, IL", "destination": "Denver, CO", "departure": "2026-10-12T20:00:00Z", "load_lbs": load, "interval": 25}
        if demo:
            body["demo"] = demo
        return self.client.post("/api/plan/", json.dumps(body), content_type="application/json")

    def test_three_routes_clear_weather(self, _):
        r = self.post()
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(len(d["routes"]), 3)
        self.assertEqual(d["recommended"], 0)  # shortest wins when risk is equal
        etas = [c["eta"] for c in d["routes"][0]["checkpoints"]]
        self.assertEqual(etas, sorted(etas))
        self.assertTrue(all(len(c["risk_by_hour"]) == 49 for c in d["routes"][0]["checkpoints"]))
        self.assertFalse(any(x["summary"]["no_travel"] for x in d["routes"]))

    def test_demo_storm_heavy_load_skips_route_a(self, _):
        d = self.post(40000, {"wind": 46}).json()
        self.assertTrue(d["routes"][0]["summary"]["no_travel"])
        self.assertNotEqual(d["recommended"], 0)

    def test_demo_storm_light_load_is_severe_not_blocked(self, _):
        s = self.post(20000, {"wind": 46}).json()["routes"][0]["summary"]
        self.assertFalse(s["no_travel"])
        self.assertGreater(s["severe_miles"], 0)

    def test_bad_input_is_400(self, _):
        r = self.client.post("/api/plan/", json.dumps({"origin": "x"}), content_type="application/json")
        self.assertEqual(r.status_code, 400)
