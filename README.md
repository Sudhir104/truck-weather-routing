# Weather-aware truck routing (React + Django)

Enter origin, destination, departure time and load weight. The app gets up to 3 routes, samples weather at 10/25/50-mile checkpoints using each checkpoint's ETA, scores risk, recommends a route, and shows a 0-48 h heatmap slider.

## Run
```
cd backend && pip install -r requirements.txt && python manage.py test routing && python manage.py runserver
cd frontend && npm install && npm run dev      # set VITE_API_URL if the API is not on :8000
```
Deploy: Django on Render/Railway (`gunicorn trucksafe.wsgi`, set `DEBUG=0`, `SECRET_KEY`), React on Vercel/Netlify (`VITE_API_URL`).

## APIs (no keys needed)
Nominatim (geocoding), OSRM demo (routes), Open-Meteo (hourly wind/rain/snowfall in mph and inches).

## Decisions
- Checkpoint risk = worst of wind, rain, snow. Load rules apply to wind only. Bands are lower-inclusive; rain/snow No Travel is strictly above the limit, wind is >= 55.
- Each checkpoint covers the miles up to the next checkpoint. "Severe miles" counts Severe and No Travel; "High miles" counts High.
- Routes with any No Travel checkpoint are skipped. The rest are ranked by severe miles, high miles, average risk (mean of checkpoints), then time.
- OSRM demo is a car profile, so durations are multiplied by 1.15 for trucks. It may return fewer than 3 alternatives; the UI says so.
- Heatmap slider = hours after departure, built from one forecast fetch, so dragging makes no network calls. Forecast is capped at 5 days.

## Demo storm
The sidebar checkbox injects 46 mph wind into the middle 30-60% of Route A only, so you can show the load rules: 40,000 lb gives No Travel (route skipped), 20,000 lb gives Severe. It is a demo override, not real weather.
