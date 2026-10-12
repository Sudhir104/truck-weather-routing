import json
from datetime import datetime, timezone

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import services as s


@csrf_exempt
@require_POST
def plan(request):
    try:
        b = json.loads(request.body)
        depart = datetime.fromisoformat(b["departure"].replace("Z", "+00:00")).astimezone(timezone.utc)
        load, step = float(b["load_lbs"]), int(b.get("interval", 25))
        demo = {k: float(x) for k, x in (b.get("demo") or {}).items() if k in ("wind", "rain", "snow")}
        if step not in (10, 25, 50):
            raise ValueError("interval must be 10, 25 or 50 miles")
        origin, dest = s.geocode(b["origin"]), s.geocode(b["destination"])
        routes = [s.build_route(r, i, depart, load, step, demo) for i, r in enumerate(s.get_routes(origin, dest))]
        return JsonResponse({"origin": origin, "destination": dest, "routes": routes, "recommended": s.recommend(routes)})
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        return JsonResponse({"error": f"Invalid request: {e}"}, status=400)
    except requests.RequestException:
        return JsonResponse({"error": "A routing or weather service is not responding. Try again."}, status=502)
