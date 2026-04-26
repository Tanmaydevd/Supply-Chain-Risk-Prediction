"""FastAPI backend — serves all ML/graph services to the React frontend.

Run:
    uvicorn api.main:app --reload --port 8000

Endpoints:
    GET  /api/metrics          — overview KPIs
    GET  /api/graph            — nodes + risk-annotated edges
    POST /api/predict          — delay probability for a route
    POST /api/simulate         — cascade failure results
    GET  /api/weather/{city}   — Open-Meteo live weather
    GET  /api/traffic/{origin}/{destination} — TomTom / heuristic
    GET  /api/shipments        — active shipment table (real + synthetic)
    GET  /api/threats          — live AI threat feed
    GET  /api/analytics        — model metrics + SHAP importances
    WS   /ws/live              — WebSocket: pushes updates every 30s
"""
from __future__ import annotations
import sys
import asyncio
import json
import random
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.weather_service import get_weather
from services.traffic_service import get_traffic
from services.prediction_service import predict_delay
from services.graph_service import get_annotated_graph, overview_metrics
from graph.simulation import cascade_failure, risk_impact
from graph.graph_builder import annotate_with_risk
from config import MODELS_DIR

app = FastAPI(title="SupplyGuard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── request schemas ────────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    origin: str
    destination: str
    weather_score: int = 1
    traffic_score: int = 1
    warehouse_load: float = 0.70

class SimulateRequest(BaseModel):
    failed_node: str
    extra_load: float = 0.15


# ── /api/metrics ───────────────────────────────────────────────────────────────
@app.get("/api/metrics")
def get_metrics():
    try:
        G = get_annotated_graph()
        m = overview_metrics()
        all_risks = [d["risk"] for _, _, d in G.edges(data=True)]
        routes_at_risk = sum(1 for r in all_risks if r >= 0.5)
        ships_at_risk  = routes_at_risk * 31
        threats = _build_threats()
        return {
            "total_active_shipments": max(m["n_edges"] * 34, 1200),
            "shipments_at_risk":      ships_at_risk,
            "ai_threats":             len(threats),
            "financial_exposure_m":   round(ships_at_risk * 22000 / 1e6, 1),
            "avg_risk":               round(m["avg_risk"], 3),
            "n_nodes":                m["n_nodes"],
            "n_edges":                m["n_edges"],
            "n_critical":             m["n_critical"],
        }
    except FileNotFoundError:
        return {"error": "Model not trained. Run python run_pipeline.py first."}


# ── /api/graph ─────────────────────────────────────────────────────────────────
@app.get("/api/graph")
def get_graph():
    G = get_annotated_graph()
    nodes = [
        {"id": n, "lat": d["lat"], "lon": d["lon"], "type": d.get("type", "hub")}
        for n, d in G.nodes(data=True)
    ]
    edges = [
        {
            "source": u, "target": v,
            "risk":   round(d["risk"], 3),
            "level":  d["risk_level"],
            "distance_km": d.get("distance", 0),
        }
        for u, v, d in G.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


# ── /api/predict ───────────────────────────────────────────────────────────────
@app.post("/api/predict")
def predict(req: PredictRequest):
    import pandas as pd
    from config import DATA_PROCESSED
    edges = pd.read_csv(DATA_PROCESSED / "edges.csv")
    direct = edges[(edges.origin == req.origin) & (edges.destination == req.destination)]
    if direct.empty:
        return {"error": f"No direct edge {req.origin} -> {req.destination}"}
    e = direct.iloc[0]
    result = predict_delay(
        distance_km=float(e.distance_km),
        weather_score=req.weather_score,
        traffic_score=req.traffic_score,
        warehouse_load=req.warehouse_load,
        hist_avg_delay_hrs=float(e.hist_avg_delay_hrs),
    )
    return {**result, "origin": req.origin, "destination": req.destination,
            "distance_km": float(e.distance_km)}


# ── /api/simulate ──────────────────────────────────────────────────────────────
@app.post("/api/simulate")
def simulate(req: SimulateRequest):
    G = get_annotated_graph()
    res = cascade_failure(G, req.failed_node)
    G_post = res["surviving_graph"]
    for u, v, d in G.edges(data=True):
        if G_post.has_edge(u, v):
            G_post[u][v]["risk"]  = d.get("risk", 0.5)
            G_post[u][v]["load"]  = 0.7
    impact = risk_impact(G, G_post, load_increase=req.extra_load)
    G_post = annotate_with_risk(G_post, default_load=min(0.7 + req.extra_load, 1.0))
    surviving_edges = [
        {"source": u, "target": v, "risk": round(d.get("risk", 0.5), 3)}
        for u, v, d in G_post.edges(data=True)
    ]
    return {
        "failed_node":        res["failed_node"],
        "cascade_order":      res["cascade_order"],
        "secondary_failures": res["secondary_failures"],
        "lost_edges":         res["lost_edges"],
        "remaining_nodes":    res["remaining_nodes"],
        "remaining_edges":    res["remaining_edges"],
        "affected_routes":    [{"from": u, "to": v} for u, v in res["affected_routes"]],
        "risk_impact":        impact[:15],
        "surviving_edges":    surviving_edges,
    }


# ── /api/weather/{city} ────────────────────────────────────────────────────────
@app.get("/api/weather/{city}")
def weather(city: str):
    return get_weather(city)


# ── /api/traffic/{origin}/{destination} ───────────────────────────────────────
@app.get("/api/traffic/{origin}/{destination}")
def traffic(origin: str, destination: str):
    return get_traffic(origin, destination)


# ── /api/threats ───────────────────────────────────────────────────────────────
def _build_threats():
    CITIES = ["Mumbai", "Delhi", "Chennai", "Kolkata", "Bangalore"]
    threats = []
    for city in CITIES:
        w = get_weather(city)
        if w["score"] >= 1:
            threats.append({
                "id":       f"weather-{city.lower()}",
                "title":    "Storm Alert" if w["score"] == 2 else "Rain / Low Visibility",
                "location": f"{city} Hub",
                "severity": "Critical" if w["score"] == 2 else "Medium",
                "orders":   random.randint(6, 40),
                "action":   "Rerouted" if w["score"] == 2 else "Delayed",
                "detail":   f"{w['precipitation_mm']}mm · {w['windspeed_kmh']}km/h wind",
                "source":   "Open-Meteo Live",
            })
    threats.append({
        "id": "strike-mumbai", "title": "Labour Strike",
        "location": "Mumbai Port", "severity": "High",
        "orders": 12, "action": "Rerouted",
        "detail": "Dock workers industrial action",
        "source": "Simulated",
    })
    return threats

@app.get("/api/threats")
def threats():
    return {"threats": _build_threats()}


# ── /api/shipments ─────────────────────────────────────────────────────────────
@app.get("/api/shipments")
def shipments():
    G = get_annotated_graph()
    PRODUCTS = [
        "Electronics", "Automotive Parts", "Pharmaceuticals", "Textiles & Apparel",
        "Industrial Machinery", "FMCG", "Semiconductors", "Cold Chain / Food",
        "Chemicals", "Steel & Metals",
    ]
    def _status(risk):
        if risk >= 0.70: return "Rerouted"
        if risk >= 0.55: return "Delayed"
        if risk >= 0.33: return "At Risk"
        return "In Transit"

    today = datetime.date.today()
    random.seed(42)
    edges_sorted = sorted(G.edges(data=True), key=lambda x: -x[2]["risk"])[:12]
    rows = []
    for i, (u, v, d) in enumerate(edges_sorted):
        eta = today + datetime.timedelta(days=random.randint(2, 14))
        rows.append({
            "id":          f"ORD-{8821 + i}",
            "product":     PRODUCTS[i % len(PRODUCTS)],
            "source":      f"{u}, IN",
            "destination": f"{v}, IN",
            "status":      _status(d["risk"]),
            "risk":        round(d["risk"], 3),
            "eta":         eta.isoformat(),
            "carrier":     random.choice(["Delhivery", "DTDC", "Blue Dart", "Ekart", "Xpressbees"]),
            "weight_kg":   round(random.uniform(0.5, 50), 1),
        })
    return {"shipments": rows, "total": len(rows)}


# ── /api/analytics ─────────────────────────────────────────────────────────────
@app.get("/api/analytics")
def analytics():
    import json as _json
    metrics_path = MODELS_DIR / "metrics.json"
    shap_path    = MODELS_DIR / "shap_importances.csv"
    fi_path      = MODELS_DIR / "feature_importances.csv"
    result = {}
    if metrics_path.exists():
        result["model_metrics"] = _json.loads(metrics_path.read_text())
    if shap_path.exists():
        import pandas as pd
        result["shap_importances"] = pd.read_csv(shap_path).to_dict(orient="records")
    if fi_path.exists():
        import pandas as pd
        result["feature_importances"] = pd.read_csv(fi_path).to_dict(orient="records")
    return result


# ── /api/nodes ─────────────────────────────────────────────────────────────────
@app.get("/api/nodes")
def nodes():
    G = get_annotated_graph()
    return {"nodes": list(G.nodes())}


# ── WebSocket /ws/live ─────────────────────────────────────────────────────────
@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """Pushes live metrics + threats every 30 seconds."""
    await websocket.accept()
    try:
        while True:
            payload = {
                "type":    "live_update",
                "metrics": get_metrics(),
                "threats": _build_threats(),
                "ts":      datetime.datetime.utcnow().isoformat(),
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass


# ── /api/realdata/aftership ────────────────────────────────────────────────────
@app.get("/api/realdata/aftership")
def aftership_trackings():
    from services.aftership_service import get_all_trackings
    return {"shipments": get_all_trackings(50)}


# ── /api/realdata/shiprocket ───────────────────────────────────────────────────
@app.get("/api/realdata/shiprocket")
def shiprocket_orders():
    from services.shiprocket_service import get_orders
    return {"shipments": get_orders(20)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
