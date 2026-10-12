import { useState } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const LEVELS = ["Low", "Moderate", "High", "Severe", "No Travel"];
const COLORS = ["#2e9e5b", "#e0c020", "#f08c1a", "#d6342c", "#4a1020"];
const LINES = ["#1f6feb", "#8957e5", "#0a8f8f"];
const inOneHour = () => new Date(Date.now() + 3600e3 - new Date().getTimezoneOffset() * 60e3).toISOString().slice(0, 16);

export default function App() {
  const [f, setF] = useState({ origin: "Chicago, IL", destination: "Denver, CO", departure: inOneHour(), load: 40000, interval: 25, demo: false });
  const [data, setData] = useState(null);
  const [sel, setSel] = useState(0);
  const [hour, setHour] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const res = await fetch(`${API}/api/plan/`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ origin: f.origin, destination: f.destination, departure: new Date(f.departure).toISOString(), load_lbs: +f.load, interval: +f.interval, demo: f.demo ? { wind: 46 } : undefined }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j.error || "Request failed");
      setData({ ...j, stamp: Date.now() }); setSel(j.recommended); setHour(0);
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  }

  const route = data?.routes.find((r) => r.id === sel);
  const sliderTime = new Date(new Date(f.departure).getTime() + hour * 3600e3).toLocaleString();

  return (<>
    <aside>
      <h1>Weather-aware truck routing</h1>
      <form onSubmit={submit}>
        <label>Origin<input value={f.origin} onChange={set("origin")} required /></label>
        <label>Destination<input value={f.destination} onChange={set("destination")} required /></label>
        <label>Departure<input type="datetime-local" value={f.departure} onChange={set("departure")} required /></label>
        <label>Load weight (lb)<input type="number" min="0" value={f.load} onChange={set("load")} required /></label>
        <label>Weather sample every
          <select value={f.interval} onChange={set("interval")}><option value="10">10 miles</option><option value="25">25 miles</option><option value="50">50 miles</option></select>
        </label>
        <label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={f.demo} onChange={(e) => setF({ ...f, demo: e.target.checked })} />Demo: 46 mph wind storm on Route A</label>
        <button disabled={busy}>{busy ? "Checking weather…" : "Find safest route"}</button>
      </form>
      {err && <p className="err">{err}</p>}
      {data?.routes.map((r) => (
        <div key={r.id} className={"card" + (r.id === sel ? " on" : "")} onClick={() => setSel(r.id)}>
          <b style={{ color: LINES[r.id] }}>Route {"ABC"[r.id]}</b>
          {r.id === data.recommended && <span className="tag">Recommended</span>}
          {r.summary.no_travel && <span className="tag bad">No Travel</span>}
          <div>{r.distance_mi} mi · {r.duration_h} h driving</div>
          <div>Severe+ miles: {r.summary.severe_miles} · High miles: {r.summary.high_miles}</div>
          <div>Average risk: {r.summary.avg_risk} / 4</div>
        </div>
      ))}
      {data && data.routes.length < 3 && <p>The routing service returned only {data.routes.length} route(s) for this trip.</p>}
    </aside>
    <main>
      <MapContainer key={data ? data.stamp : "init"} className="map"
        {...(data ? { bounds: [data.origin, data.destination], boundsOptions: { padding: [40, 40] } } : { center: [39.5, -98.35], zoom: 4 })}>
        <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap contributors" />
        {data?.routes.map((r) => (
          <Polyline key={r.id} positions={r.geometry} eventHandlers={{ click: () => setSel(r.id) }}
            pathOptions={{ color: LINES[r.id], weight: r.id === sel ? 7 : 3, opacity: r.id === sel ? 0.9 : 0.45 }} />
        ))}
        {route?.checkpoints.map((c, i) => (
          <CircleMarker key={"h" + i} center={[c.lat, c.lon]} radius={22}
            pathOptions={{ stroke: false, fillColor: COLORS[c.risk_by_hour[hour]], fillOpacity: 0.3 }} />
        ))}
        {route?.checkpoints.map((c, i) => (
          <CircleMarker key={"p" + i} center={[c.lat, c.lon]} radius={5}
            pathOptions={{ color: "#fff", weight: 1, fillColor: COLORS[c.risk], fillOpacity: 1 }}>
            <Tooltip>
              <b>Mile {c.mile}: {LEVELS[c.risk]}</b><br />ETA {new Date(c.eta).toLocaleString()}<br />
              Wind {c.wind} mph · Rain {c.rain} in/hr · Snow {c.snow} in/hr
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
      <div className="bar">
        <label>Forecast heatmap: {hour} h after departure ({sliderTime})
          <input type="range" min="0" max="48" value={hour} disabled={!route} onChange={(e) => setHour(+e.target.value)} />
        </label>
        {LEVELS.map((l, i) => <span key={l} style={{ marginRight: 12 }}><span style={{ color: COLORS[i] }}>●</span> {l}</span>)}
      </div>
    </main>
  </>);
}
