# AI-Powered Supply Chain Risk Prediction System
## Detailed Step-by-Step Implementation Playbook

> **Project owner:** tnau · **Course:** 6th Sem Main EL · **Stack:** Python + Streamlit + scikit-learn / XGBoost + NetworkX + Folium
> **Document version:** 1.0 (2026-04-26)

---

## 0. How to read this document

This is the **single source of truth** for building the project. Every other artifact (code, slides, viva script) follows from here.

The playbook is organized in three layers:

1. **What & Why** — Sections 1–4 (project intent, architecture, tech rationale).
2. **How** — Sections 5–11 (week-by-week build plan with file-level instructions and code snippets).
3. **Defense** — Sections 12–15 (testing, demo script, viva answers, risk register).

If you only have 30 minutes, read sections 1, 3, 6, and 13. Then come back later.

---

## 1. Executive Summary

### 1.1 The pitch in one sentence
> A decision-support system that, given a shipment route, predicts the likelihood of delay, scores end-to-end risk across the logistics network, and — when risk is high — recommends a safer alternate route, all visualized on an interactive map with cascading-failure simulation.

### 1.2 Why this is more than "just risk prediction"
Most student logistics projects stop at "predict if a shipment is late." This one is positioned as **3-layer intelligence**:

| Layer | Question it answers | Output |
|---|---|---|
| **L1 — Delay Prediction** | *Will this shipment be late?* | Delay probability, expected delay hours, risk category (Low/Med/High) |
| **L2 — Network Risk** | *How fragile is the whole supply chain right now?* | Per-route risk score, list of critical hubs, list of bottleneck edges |
| **L3 — Decision Support** | *What should we do about it?* | Suggested alternate route + cascading-failure simulation if a node goes down |

Adding L3 is the differentiator that turns this from a *report* into a *recommender*.

### 1.3 Final demo flow (this is what the panel will see)
1. Open dashboard → see overview metrics (total nodes, routes, current critical hubs).
2. Go to **Predict** page → enter Bangalore → Chennai, traffic=High, weather=Rain → see "Delay 82%, Risk High".
3. System auto-suggests **Bangalore → Hyderabad → Chennai** as alternate.
4. Switch to **Map** → see nodes/edges colored by risk.
5. Switch to **Simulate** → kill "Chennai" node → see which routes break and which hubs absorb the load.
6. Switch to **Analytics** → see top-10 risky routes, top critical hubs, delay trend chart.

If you can deliver those six steps live, the project succeeds.

---

## 2. Revised System Architecture (Streamlit-first)

The original prompt mentioned React + FastAPI. We are simplifying to **Streamlit-only** because:
- Single language (Python) end-to-end → faster build, fewer integration bugs.
- Streamlit's built-in support for `folium`, `plotly`, `pandas` means you write zero frontend boilerplate.
- A Streamlit multi-page app looks polished enough for a college viva and is deployable in one click to Streamlit Community Cloud.
- You can still call out in your viva: *"The architecture is modular — services/ contains pure Python so we can swap Streamlit for a React+FastAPI stack later without rewriting any business logic."* That makes the simplification a feature, not a limitation.

### 2.1 Logical architecture
```
                ┌────────────────────────────────────────────────┐
                │            Streamlit Multi-Page App             │
                │  Home · Predict · Map · Simulate · Analytics    │
                └───────────────────────┬────────────────────────┘
                                        │ (function calls, in-process)
                ┌───────────────────────┼────────────────────────┐
                │                       │                        │
                ▼                       ▼                        ▼
       ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
       │  ML Service  │         │ Graph Service│         │ Routing Svc  │
       │ (predict.py) │         │ (graph_      │         │ (router.py)  │
       │              │         │  service.py) │         │              │
       └──────┬───────┘         └──────┬───────┘         └──────┬───────┘
              │                        │                        │
              ▼                        ▼                        ▼
     ┌────────────────┐       ┌────────────────┐       ┌────────────────┐
     │ trained_models │       │  NetworkX      │       │ Dijkstra /     │
     │   *.joblib     │       │  Graph object  │       │ A* algorithms  │
     └────────────────┘       └────────────────┘       └────────────────┘
                                        │
                                        ▼
                              ┌────────────────────┐
                              │  data/processed/   │
                              │  shipments.csv     │
                              │  nodes.csv         │
                              │  edges.csv         │
                              └────────────────────┘
```

### 2.2 Why this layering matters
- **`app/` (Streamlit pages)** is *only* presentation — every page calls into `services/`.
- **`services/`** is *pure Python* — no Streamlit imports, no UI code. This is what you'd lift-and-shift into a FastAPI backend later.
- **`ml/` and `graph/`** are *training/build* code (offline). They produce artifacts that `services/` loads at runtime.

This separation is what lets you say "we built it modular" honestly in viva.

---

## 3. Tech Stack & Why Each Choice

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.10+ | One language for ML + graph + UI |
| UI | Streamlit ≥ 1.30 | Multi-page apps, instant data widgets, Folium support |
| Maps | Folium + streamlit-folium | Leaflet under the hood, plays nicely with Streamlit |
| Charts | Plotly Express | Interactive, hover tooltips, looks better than matplotlib |
| ML — baseline | scikit-learn `LogisticRegression` | Sanity-check; trains in <1 sec |
| ML — main | `RandomForestClassifier` | Non-linear, handles mixed features, easy to explain |
| ML — stretch | `XGBoostClassifier` | "We tried gradient boosting too" — good viva point |
| Graph | NetworkX 3.x | De facto standard for this scale (≤ ~500 nodes) |
| Routing | NetworkX `shortest_path` (Dijkstra) | Built-in, weight-aware |
| Data | pandas + CSV → SQLite later | Don't over-engineer for MVP |
| Persistence | `joblib` for models, `pickle` for graph | Standard practice |
| Config | `pydantic-settings` or simple `config.py` | Centralizes hardcoded constants |
| Testing | `pytest` | A handful of unit tests = professionalism points |

### 3.1 Libraries to **avoid** for now
- ❌ TensorFlow / PyTorch — overkill for tabular delay prediction.
- ❌ Graph Neural Networks — list as "future work" only.
- ❌ Docker — not required for a college EL; mention as future enhancement if asked.

---

## 4. What does the project actually do? (the 3-layer answer)

This is the answer to your earlier question *"is it just risk prediction?"* — copy this into your report verbatim.

### Layer 1 — Delay Prediction (per-shipment, supervised ML)
**Inputs:** origin, destination, distance_km, traffic_score (0–2), weather_score (0–2), warehouse_load (0–1), historical_avg_delay_hrs.
**Model:** RandomForestClassifier trained on historical shipment data with binary `delayed` label.
**Outputs:**
- `delay_probability` (0–1)
- `expected_delay_hours` (regression head — optional v2)
- `risk_level` ∈ {Low, Medium, High} (thresholded probability)

### Layer 2 — Network Risk (graph-level, structural)
**Inputs:** the full shipment network as a weighted directed graph.
**Computation:**
- Edge weights = `delay_probability` from L1 (so the graph is *informed by* ML predictions).
- Compute **degree centrality**, **betweenness centrality**, **closeness centrality**.
- A node with high betweenness *and* high adjacent edge risk = **critical hub**.
- An edge with high weight on a unique shortest path = **bottleneck**.

**Outputs:**
- Ranked list of critical hubs.
- Ranked list of bottleneck edges.
- Per-route aggregate risk score (sum of edge weights along the path).

### Layer 3 — Decision Support (cascading + alternate routes)
**Cascading Failure:**
- User picks a node to "fail" (e.g., Chennai warehouse strike).
- Remove node from graph, recompute connectivity, list disconnected pairs and rerouted edges.

**Alternate Route Recommendation:**
- Run Dijkstra on the graph using `(distance × (1 + risk_weight))` as edge cost.
- Return top-1 alternate path that avoids the high-risk edge / failed node.

**Example output the dashboard shows:**
```
Route requested: Bangalore → Chennai
Direct delay probability: 82%   Risk: HIGH
Suggested alternate: Bangalore → Hyderabad → Chennai
   Combined risk: 41%   Extra distance: +180 km
```

That's the headline screenshot for your report.

---

## 5. Folder Structure (final, after scaffold)

```
supply-chain-risk/
│
├── DESIGN.md                  ← this file
├── README.md                  ← quickstart
├── requirements.txt
├── .gitignore
│
├── config.py                  ← single place for thresholds, paths, city coords
│
├── data/
│   ├── raw/                   ← original CSVs (Olist or synthetic)
│   ├── processed/             ← cleaned, feature-engineered
│   │   ├── shipments.csv
│   │   ├── nodes.csv          ← city, lat, lon, type
│   │   └── edges.csv          ← origin, dest, distance, hist_delay
│   └── README.md              ← describes each file's schema
│
├── ml/
│   ├── __init__.py
│   ├── preprocess.py          ← clean + feature engineer
│   ├── train_model.py         ← trains RF/XGB, saves joblib
│   ├── evaluate.py            ← prints accuracy/F1/confusion matrix
│   └── notebooks/
│       └── 01_eda.ipynb       ← optional EDA for report screenshots
│
├── graph/
│   ├── __init__.py
│   ├── graph_builder.py       ← build NetworkX graph from edges.csv
│   ├── analytics.py           ← centrality, bottlenecks
│   ├── simulation.py          ← cascading failure
│   └── routing.py             ← Dijkstra alternate path
│
├── services/                  ← pure Python, no Streamlit
│   ├── __init__.py
│   ├── prediction_service.py  ← loads model, exposes predict()
│   ├── graph_service.py       ← loads graph, exposes query funcs
│   └── routing_service.py     ← thin wrapper over graph.routing
│
├── trained_models/
│   └── delay_rf.joblib        ← created by ml/train_model.py
│
├── app/                       ← Streamlit UI lives here
│   ├── Home.py                ← entrypoint: `streamlit run app/Home.py`
│   ├── pages/
│   │   ├── 1_Predict.py
│   │   ├── 2_Map.py
│   │   ├── 3_Simulate.py
│   │   └── 4_Analytics.py
│   └── components/            ← reusable Streamlit fragments
│       ├── metrics_card.py
│       └── risk_badge.py
│
└── tests/
    ├── test_preprocess.py
    ├── test_graph.py
    └── test_routing.py
```

Why this layout?
- `app/` matches Streamlit's expected multi-page convention (`pages/` auto-discovered).
- `services/` is the API surface — every Streamlit page calls into here, never directly into `ml/` or `graph/`.
- `data/`, `ml/`, `graph/` are independent enough that one teammate could own each.

---

## 6. Data Strategy — *where do nodes and edges actually come from?*

This is the question you asked, and it's the right one. Here is the staged answer, from quickest to most realistic.

### 6.1 Stage A — Synthetic seed data (Day 1, mandatory)
Create a **hand-built** small graph of ~15 Indian cities. This unblocks every other module instantly.

`data/processed/nodes.csv`:
```csv
city,lat,lon,type
Bangalore,12.9716,77.5946,hub
Chennai,13.0827,80.2707,port
Hyderabad,17.3850,78.4867,hub
Mumbai,19.0760,72.8777,port
Delhi,28.7041,77.1025,hub
Kolkata,22.5726,88.3639,port
Pune,18.5204,73.8567,warehouse
Ahmedabad,23.0225,72.5714,warehouse
Jaipur,26.9124,75.7873,warehouse
Lucknow,26.8467,80.9462,warehouse
Coimbatore,11.0168,76.9558,warehouse
Kochi,9.9312,76.2673,port
Nagpur,21.1458,79.0882,hub
Bhopal,23.2599,77.4126,warehouse
Visakhapatnam,17.6868,83.2185,port
```

`data/processed/edges.csv` (sample — write ~30 edges):
```csv
origin,destination,distance_km,hist_avg_delay_hrs
Bangalore,Chennai,346,4.2
Bangalore,Hyderabad,569,3.1
Hyderabad,Chennai,627,5.0
Mumbai,Pune,148,1.2
Mumbai,Ahmedabad,524,2.8
...
```

### 6.2 Stage B — Synthetic shipment history (Day 2)
Generate ~5,000 fake shipments programmatically by sampling routes from edges and injecting realistic noise:

```python
# pseudocode in ml/preprocess.py::generate_synthetic_shipments
for _ in range(5000):
    edge = random.choice(edges)
    weather = random.choices([0,1,2], weights=[0.6,0.3,0.1])[0]
    traffic = random.choices([0,1,2], weights=[0.5,0.35,0.15])[0]
    warehouse_load = random.uniform(0.3, 1.0)
    # delay probability rule (this is the "ground truth" we'll hide from the model)
    p = 0.05 + 0.15*weather + 0.20*traffic + 0.30*max(0,warehouse_load-0.7)
    delayed = 1 if random.random() < p else 0
```

Why synthesize? Because (a) Olist is Brazilian and the city names won't match your map; (b) you can control the signal so the model actually learns something demonstrable.

### 6.3 Stage C — Optional real data (only if time permits)
If you finish Module 1–4 with a week to spare, layer in:
- **Olist dataset** (Kaggle) — extract `seller_city` → `customer_city` pairs; map to your 15-city graph.
- **OpenStreetMap Nominatim** for real lat/lon if you expand beyond 15 cities.

Don't start here. Stage A+B is enough for a working demo.

### 6.4 Optional real-time integrations (Future Work slide)
- **OpenWeatherMap API** — current weather per node.
- **TomTom Traffic API** — current traffic per edge.
- **NewsAPI** — strike/disaster headlines per region.

List these in the report as "future enhancements"; do **not** implement for MVP.

---

## 7. Week-by-Week Build Plan (6 weeks)

This assumes ~10 hrs/week. Compress to 3 weeks if working full-time.

| Week | Focus | Deliverable | Demo-able? |
|---|---|---|---|
| 1 | Setup + Data | Folder scaffold, synthetic data generator, EDA notebook | No |
| 2 | ML Pipeline | Trained delay model, evaluate.py prints F1≥0.80 | Backend only |
| 3 | Graph Engine | NetworkX graph, centrality, bottleneck detection | Backend only |
| 4 | Simulation + Routing | Cascading failure + Dijkstra alternate route | Backend only |
| 5 | Streamlit UI | All 5 pages wired, map + simulation working | **YES — first end-to-end demo** |
| 6 | Polish + Report | Tests, docstrings, README, viva slides | Final demo |

### 7.1 Critical path (don't skip these even if you compress)
1. End of Week 1: `data/processed/edges.csv` and `nodes.csv` exist.
2. End of Week 2: `trained_models/delay_rf.joblib` exists and `predict()` returns sensible numbers.
3. End of Week 4: `services/routing_service.py::suggest_alternate()` returns a valid path.
4. End of Week 5: All 5 Streamlit pages run without errors when you `streamlit run app/Home.py`.

If any of those four checkpoints slip, cut features (drop XGBoost, drop simulation animations) — do not skip them.

---

## 8. Module 1 — Data Pipeline (Week 1)

### 8.1 Goals
- Produce reproducible `nodes.csv`, `edges.csv`, `shipments.csv`.
- Encode categorical features (weather, traffic) consistently.

### 8.2 Files to write

#### `config.py`
```python
from pathlib import Path

ROOT = Path(__file__).parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "trained_models"

WEATHER_MAP = {"Sunny": 0, "Cloudy": 0, "Rain": 1, "Storm": 2}
TRAFFIC_MAP = {"Low": 0, "Medium": 1, "High": 2}

RISK_THRESHOLDS = {"low": 0.33, "medium": 0.66}  # >= 0.66 → High
N_SYNTHETIC_SHIPMENTS = 5000
RANDOM_SEED = 42
```

#### `ml/preprocess.py` — key functions
```python
import pandas as pd, numpy as np
from config import DATA_PROCESSED, RANDOM_SEED, N_SYNTHETIC_SHIPMENTS

def load_nodes() -> pd.DataFrame: ...
def load_edges() -> pd.DataFrame: ...

def generate_synthetic_shipments(n=N_SYNTHETIC_SHIPMENTS, seed=RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    edges = load_edges()
    rows = []
    for _ in range(n):
        e = edges.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
        weather = rng.choice([0,1,2], p=[0.6,0.3,0.1])
        traffic = rng.choice([0,1,2], p=[0.5,0.35,0.15])
        wh_load = rng.uniform(0.3, 1.0)
        p = 0.05 + 0.15*weather + 0.20*traffic + 0.30*max(0, wh_load-0.7)
        delayed = int(rng.random() < p)
        rows.append({
            "origin": e.origin, "destination": e.destination,
            "distance_km": e.distance_km, "weather_score": weather,
            "traffic_score": traffic, "warehouse_load": wh_load,
            "hist_avg_delay_hrs": e.hist_avg_delay_hrs,
            "delayed": delayed,
        })
    df = pd.DataFrame(rows)
    df.to_csv(DATA_PROCESSED / "shipments.csv", index=False)
    return df

def feature_columns():
    return ["distance_km","weather_score","traffic_score","warehouse_load","hist_avg_delay_hrs"]
```

### 8.3 Acceptance test
Run:
```bash
python -c "from ml.preprocess import generate_synthetic_shipments; print(generate_synthetic_shipments().head())"
```
You should see 5 rows with a `delayed` column that's a mix of 0s and 1s.

### 8.4 Common pitfall
Don't forget to save `shipments.csv` to disk — Module 2 reads it, not the in-memory DataFrame.

---

## 9. Module 2 — ML Pipeline (Week 2)

### 9.1 Goals
- Train RandomForest baseline → save to `trained_models/delay_rf.joblib`.
- Print accuracy, precision, recall, F1, confusion matrix.
- Aim for F1 ≥ 0.80 on synthetic data (it'll be easy because we generated the labels with a known rule).

### 9.2 `ml/train_model.py`
```python
import joblib, pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from config import DATA_PROCESSED, MODELS_DIR, RANDOM_SEED
from ml.preprocess import feature_columns

def train():
    df = pd.read_csv(DATA_PROCESSED / "shipments.csv")
    X, y = df[feature_columns()], df["delayed"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2,
                                          random_state=RANDOM_SEED, stratify=y)
    model = RandomForestClassifier(n_estimators=200, random_state=RANDOM_SEED)
    model.fit(Xtr, ytr)
    yp = model.predict(Xte)
    print(classification_report(yte, yp))
    print(confusion_matrix(yte, yp))
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODELS_DIR / "delay_rf.joblib")
    return model

if __name__ == "__main__":
    train()
```

### 9.3 `services/prediction_service.py`
```python
import joblib, numpy as np
from config import MODELS_DIR, RISK_THRESHOLDS
from ml.preprocess import feature_columns

_MODEL = None
def _model():
    global _MODEL
    if _MODEL is None:
        _MODEL = joblib.load(MODELS_DIR / "delay_rf.joblib")
    return _MODEL

def predict_delay(distance_km, weather_score, traffic_score,
                  warehouse_load, hist_avg_delay_hrs) -> dict:
    m = _model()
    x = np.array([[distance_km, weather_score, traffic_score,
                   warehouse_load, hist_avg_delay_hrs]])
    p = float(m.predict_proba(x)[0,1])
    if p >= RISK_THRESHOLDS["medium"]:
        level = "High"
    elif p >= RISK_THRESHOLDS["low"]:
        level = "Medium"
    else:
        level = "Low"
    return {"delay_probability": round(p,3),
            "risk_score": int(round(p*100)),
            "risk_level": level}
```

### 9.4 Stretch goal
Also train `XGBClassifier` and pick the better F1 — gives you a viva talking point ("we benchmarked two models").

### 9.5 Acceptance test
```python
from services.prediction_service import predict_delay
print(predict_delay(346, weather_score=1, traffic_score=2,
                    warehouse_load=0.9, hist_avg_delay_hrs=4.2))
# expect risk_level == "High"
```

---

## 10. Module 3 — Graph Engine (Week 3)

### 10.1 `graph/graph_builder.py`
```python
import networkx as nx, pandas as pd
from config import DATA_PROCESSED

def build_graph() -> nx.DiGraph:
    nodes = pd.read_csv(DATA_PROCESSED / "nodes.csv")
    edges = pd.read_csv(DATA_PROCESSED / "edges.csv")
    G = nx.DiGraph()
    for _, n in nodes.iterrows():
        G.add_node(n.city, lat=n.lat, lon=n.lon, type=n.type)
    for _, e in edges.iterrows():
        G.add_edge(e.origin, e.destination,
                   distance=e.distance_km,
                   hist_delay=e.hist_avg_delay_hrs)
    return G
```

### 10.2 `graph/analytics.py`
```python
import networkx as nx

def centrality(G) -> dict:
    return {
        "degree": nx.degree_centrality(G),
        "betweenness": nx.betweenness_centrality(G, weight="distance"),
        "closeness": nx.closeness_centrality(G, distance="distance"),
    }

def critical_hubs(G, top_n=5):
    bc = nx.betweenness_centrality(G, weight="distance")
    return sorted(bc.items(), key=lambda kv: kv[1], reverse=True)[:top_n]

def bottleneck_edges(G, top_n=5):
    eb = nx.edge_betweenness_centrality(G, weight="distance")
    return sorted(eb.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
```

### 10.3 Wire ML into the graph (this is the magic step)
After training Module 2, decorate each edge with a *predicted* risk weight based on **average conditions**, so the graph carries ML signal:

```python
# graph/graph_builder.py — add this function
from services.prediction_service import predict_delay

def annotate_with_risk(G, default_weather=1, default_traffic=1, default_load=0.7):
    for u,v,d in G.edges(data=True):
        r = predict_delay(d["distance"], default_weather, default_traffic,
                          default_load, d["hist_delay"])
        d["risk"] = r["delay_probability"]
        d["risk_level"] = r["risk_level"]
    return G
```

Now `risk` is an edge attribute and we can use it for shortest-path-by-risk.

---

## 11. Module 4 — Simulation + Alternate Routing (Week 4)

### 11.1 `graph/simulation.py`
```python
import networkx as nx

def cascade_failure(G: nx.DiGraph, failed_node: str) -> dict:
    H = G.copy()
    affected_in  = list(H.in_edges(failed_node))
    affected_out = list(H.out_edges(failed_node))
    H.remove_node(failed_node)

    # find pairs that became disconnected
    isolated = []
    for n in H.nodes:
        if n == failed_node: continue
        if H.in_degree(n) == 0 and H.out_degree(n) == 0:
            isolated.append(n)

    return {
        "failed_node": failed_node,
        "lost_edges": len(affected_in) + len(affected_out),
        "affected_routes": [(u,v) for u,v in (affected_in + affected_out)],
        "isolated_nodes": isolated,
    }
```

### 11.2 `graph/routing.py`
```python
import networkx as nx

def suggest_alternate(G, origin, destination, avoid_node=None, weight="risk"):
    H = G.copy()
    if avoid_node and avoid_node in H:
        H.remove_node(avoid_node)
    try:
        path = nx.shortest_path(H, origin, destination, weight=weight)
        cost = nx.shortest_path_length(H, origin, destination, weight=weight)
        return {"path": path, "total_risk": round(cost,3)}
    except nx.NetworkXNoPath:
        return {"path": None, "total_risk": None}
```

### 11.3 `services/routing_service.py` — the "decision support" facade
```python
from graph.graph_builder import build_graph, annotate_with_risk
from graph.routing import suggest_alternate

_G = None
def _graph():
    global _G
    if _G is None:
        _G = annotate_with_risk(build_graph())
    return _G

def best_route(origin, destination):
    G = _graph()
    direct = suggest_alternate(G, origin, destination, weight="risk")
    return direct  # could extend: top-k k-shortest paths
```

### 11.4 Acceptance test (this is your headline demo)
```python
from services.routing_service import best_route
from graph.simulation import cascade_failure
from graph.graph_builder import build_graph

print(best_route("Bangalore","Chennai"))
# → {"path": ["Bangalore","Chennai"] or ["Bangalore","Hyderabad","Chennai"], ...}

print(cascade_failure(build_graph(), "Chennai"))
# → {"failed_node":"Chennai","lost_edges":...,"isolated_nodes":[...]}
```

---

## 12. Module 5 — Streamlit Dashboard (Week 5)

Streamlit auto-discovers `pages/` next to the entrypoint. The sidebar shows Home + each page in alphabetical order — that's why files are prefixed `1_`, `2_`, etc.

### 12.1 `app/Home.py` (entrypoint)
```python
import streamlit as st
from services.graph_service import overview_metrics

st.set_page_config(page_title="Supply Chain Risk Intelligence",
                   page_icon="📦", layout="wide")
st.title("📦 Supply Chain Risk Intelligence")
st.markdown("AI-powered delay prediction, network risk analysis, and decision support.")

m = overview_metrics()
c1,c2,c3,c4 = st.columns(4)
c1.metric("Cities (nodes)", m["n_nodes"])
c2.metric("Routes (edges)", m["n_edges"])
c3.metric("Avg route risk", f"{m['avg_risk']:.0%}")
c4.metric("Critical hubs", m["n_critical"])

st.info("Use the sidebar → Predict, Map, Simulate, Analytics.")
```

### 12.2 `app/pages/1_Predict.py`
```python
import streamlit as st, pandas as pd
from services.prediction_service import predict_delay
from services.routing_service import best_route
from config import DATA_PROCESSED

nodes = pd.read_csv(DATA_PROCESSED/"nodes.csv")["city"].tolist()
edges = pd.read_csv(DATA_PROCESSED/"edges.csv")

st.title("🔮 Predict Delay & Get Alternate Route")

col1,col2 = st.columns(2)
origin = col1.selectbox("Origin", nodes)
dest   = col2.selectbox("Destination", [c for c in nodes if c != origin])

weather = st.select_slider("Weather", ["Sunny","Cloudy","Rain","Storm"], "Cloudy")
traffic = st.select_slider("Traffic", ["Low","Medium","High"], "Medium")
load    = st.slider("Warehouse load", 0.0, 1.0, 0.7)

if st.button("Predict"):
    e = edges[(edges.origin==origin)&(edges.destination==dest)]
    if e.empty:
        st.warning("No direct edge — alternate route needed.")
        alt = best_route(origin, dest)
        st.write(alt)
    else:
        e = e.iloc[0]
        from config import WEATHER_MAP, TRAFFIC_MAP
        r = predict_delay(e.distance_km,
                          WEATHER_MAP[weather], TRAFFIC_MAP[traffic],
                          load, e.hist_avg_delay_hrs)
        c1,c2,c3 = st.columns(3)
        c1.metric("Delay probability", f"{r['delay_probability']:.0%}")
        c2.metric("Risk score", r["risk_score"])
        c3.metric("Risk level", r["risk_level"])

        if r["risk_level"] == "High":
            st.warning("High risk — checking for safer alternate route…")
            alt = best_route(origin, dest)
            st.success(f"Suggested: {' → '.join(alt['path'])} (risk={alt['total_risk']})")
```

### 12.3 `app/pages/2_Map.py`
```python
import streamlit as st, pandas as pd, folium
from streamlit_folium import st_folium
from services.graph_service import get_annotated_graph

st.title("🗺️ Network Map")
G = get_annotated_graph()
m = folium.Map(location=[22.0,79.0], zoom_start=5, tiles="cartodbpositron")

for n,d in G.nodes(data=True):
    folium.CircleMarker([d["lat"],d["lon"]], radius=6,
                        popup=n, color="blue", fill=True).add_to(m)

def color(r):
    return "green" if r<0.33 else "orange" if r<0.66 else "red"

for u,v,d in G.edges(data=True):
    a, b = G.nodes[u], G.nodes[v]
    folium.PolyLine([(a["lat"],a["lon"]),(b["lat"],b["lon"])],
                    color=color(d["risk"]), weight=3,
                    tooltip=f"{u}→{v} risk={d['risk']:.0%}").add_to(m)

st_folium(m, width=1200, height=600)
```

### 12.4 `app/pages/3_Simulate.py`
```python
import streamlit as st
from services.graph_service import all_nodes
from graph.simulation import cascade_failure
from graph.graph_builder import build_graph

st.title("💥 Cascading Failure Simulation")
node = st.selectbox("Pick a node to fail", all_nodes())
if st.button("Simulate failure"):
    res = cascade_failure(build_graph(), node)
    c1,c2 = st.columns(2)
    c1.metric("Lost edges", res["lost_edges"])
    c2.metric("Newly isolated nodes", len(res["isolated_nodes"]))
    st.write("**Affected routes:**", res["affected_routes"])
    st.write("**Isolated nodes:**", res["isolated_nodes"] or "None")
```

### 12.5 `app/pages/4_Analytics.py`
```python
import streamlit as st, plotly.express as px, pandas as pd
from services.graph_service import get_annotated_graph
from graph.analytics import critical_hubs, bottleneck_edges

st.title("📊 Analytics")
G = get_annotated_graph()

st.subheader("Top critical hubs (betweenness)")
hubs = pd.DataFrame(critical_hubs(G,5), columns=["city","centrality"])
st.plotly_chart(px.bar(hubs, x="city", y="centrality"), use_container_width=True)

st.subheader("Top risky routes")
risky = sorted([(u,v,d["risk"]) for u,v,d in G.edges(data=True)],
               key=lambda x:-x[2])[:10]
df = pd.DataFrame(risky, columns=["origin","destination","risk"])
st.dataframe(df, use_container_width=True)
```

### 12.6 `services/graph_service.py` (glue layer)
```python
from graph.graph_builder import build_graph, annotate_with_risk
from graph.analytics import critical_hubs

_G = None
def get_annotated_graph():
    global _G
    if _G is None:
        _G = annotate_with_risk(build_graph())
    return _G

def all_nodes():
    return list(get_annotated_graph().nodes)

def overview_metrics():
    G = get_annotated_graph()
    risks = [d["risk"] for _,_,d in G.edges(data=True)]
    return {
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "avg_risk": sum(risks)/len(risks) if risks else 0,
        "n_critical": len(critical_hubs(G,5)),
    }
```

---

## 13. Testing Strategy

### 13.1 Unit tests (Week 6)
A handful is enough — quality over quantity.

`tests/test_preprocess.py`:
```python
def test_synthetic_shipments_has_label():
    from ml.preprocess import generate_synthetic_shipments
    df = generate_synthetic_shipments(n=100, seed=0)
    assert "delayed" in df.columns
    assert df["delayed"].nunique() == 2
```

`tests/test_graph.py`:
```python
def test_graph_builds_with_all_nodes():
    from graph.graph_builder import build_graph
    G = build_graph()
    assert G.number_of_nodes() >= 10
    assert G.number_of_edges() > 0
```

`tests/test_routing.py`:
```python
def test_alternate_route_exists():
    from services.routing_service import best_route
    r = best_route("Bangalore","Chennai")
    assert r["path"] is not None
```

Run with `pytest tests/`.

### 13.2 Integration / scenario tests (the demo's safety net)
Document these in `tests/scenarios.md` and run manually before the viva:

| Scenario | Action | Expected |
|---|---|---|
| High-risk inputs | weather=Storm, traffic=High, load=0.95 | risk_level == High |
| Low-risk inputs | weather=Sunny, traffic=Low, load=0.4 | risk_level == Low |
| Direct route exists, low risk | Bangalore→Chennai sunny | suggested = direct |
| High direct risk | Bangalore→Chennai storm | suggested = via Hyderabad |
| Kill Chennai | Simulate Chennai failure | ≥2 routes lost, alternate via Hyderabad |
| Kill non-hub | Simulate Bhopal failure | minimal isolation |

### 13.3 Model evaluation report
Save `ml/evaluation_report.txt` with classification report + confusion matrix. Include this as an appendix in your project report.

---

## 14. Demo Script for Viva (memorize this)

**(0:00 – 0:30) — Pitch**
> "Our project predicts shipment delays, but more importantly it tells the operator what to do about it. There are three layers: ML-based delay prediction, graph-based network risk, and decision support — alternate routing plus failure simulation."

**(0:30 – 1:30) — Predict page**
- Open Predict, choose Bangalore → Chennai, Storm + High traffic + load 0.9.
- Read aloud: "Random Forest predicts 87% delay probability, classifies as High."
- Click Predict — system auto-suggests Bangalore → Hyderabad → Chennai.
- *Talking point:* "Note the system didn't just warn us — it gave us a concrete alternative."

**(1:30 – 2:30) — Map**
- Show colored map. Point out red edges = high risk.
- *Talking point:* "Edge colors come from running the trained model across the network with average conditions, so the graph itself is ML-informed."

**(2:30 – 3:30) — Simulation**
- Pick Chennai → Simulate.
- Show lost edges and isolated nodes.
- *Talking point:* "This is cascading failure analysis — useful for what-if planning before strikes, floods, or warehouse outages."

**(3:30 – 4:00) — Analytics**
- Show top critical hubs bar chart.
- *Talking point:* "Betweenness centrality identifies hubs whose failure would hurt the most."

**(4:00 – 5:00) — Architecture & defense**
- Open `DESIGN.md` section 2.
- Mention the three-layer Streamlit + services + ML/graph split.
- Mention "future work: real-time APIs, GNNs, IoT GPS."

### 14.1 Likely viva questions and crisp answers
| Q | Crisp answer |
|---|---|
| Why Random Forest? | "Handles non-linear interactions, robust to feature scales, easy to explain. We also benchmarked logistic regression and XGBoost." |
| How is risk different from delay? | "Delay is a per-shipment probability. Risk is an aggregate over a route, weighted by graph structure — a high-betweenness edge with high delay probability is doubly risky." |
| Why NetworkX, not a database? | "MVP scale (15 nodes, ~30 edges). NetworkX runs centrality in milliseconds. We'd switch to Neo4j past ~10K nodes." |
| Where's the real-time data? | "Phase 2 — APIs are listed in the design. The architecture isolates the data layer so swapping in OpenWeatherMap is a single function." |
| What if model is wrong? | "Three mitigations: (1) probability output, not binary, so users see uncertainty; (2) graph layer is structural, doesn't depend on the model; (3) suggested alternates are always returned, so the user has a fallback." |
| Could you use a neural network? | "Yes — for tabular data RF/XGB usually win; for the graph, GNNs would be the right next step. We list both in future work." |

---

## 15. Risk Register & Common Pitfalls

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Streamlit reloads model on every page change | High | Slow UX | Use `@st.cache_resource` on `_graph()` and `_model()` |
| Folium map blanks out on rerun | Medium | Demo bug | Wrap `st_folium` with `key=` to force consistent state |
| Synthetic data too easy → 99% F1 | High | Looks fishy in viva | Add 10% label noise; show 80–90% F1 with honest evaluation |
| Cascading failure isolates everything | Medium | Boring demo | Pre-pick "good" demo nodes (Chennai, Mumbai) that produce interesting cascades |
| `pages/` not auto-detected | Low | UI breaks | Run from project root: `streamlit run app/Home.py`; numeric prefixes are required |
| XGBoost install fails on Windows | Medium | Block Module 2 stretch | Skip XGBoost — RF alone is enough; mention as future |
| Last-minute import errors | High | Demo dies | Always test the *full* `streamlit run` chain the night before |

### 15.1 The night-before checklist
- [ ] `pip install -r requirements.txt` from a clean venv works.
- [ ] `python ml/preprocess.py && python ml/train_model.py` runs end-to-end.
- [ ] `streamlit run app/Home.py` opens without errors.
- [ ] All 4 sidebar pages load.
- [ ] Predict button returns a result.
- [ ] Map renders with at least one red edge.
- [ ] Simulate shows non-empty result for Chennai.
- [ ] Screenshots saved in `report/screenshots/` for the report.

---

## 16. Future Enhancements (the "Future Work" slide)

1. **Real-time data ingestion** — OpenWeatherMap + TomTom + NewsAPI background jobs refreshing edge attributes hourly.
2. **Graph Neural Networks** — message-passing on the supply graph for delay prediction; compare to RF baseline.
3. **IoT truck GPS feed** — live shipment positions overlaid on the map; ETA predictions.
4. **LLM-based disruption summarization** — feed news headlines + model outputs into Claude/GPT to produce a daily English summary.
5. **Multi-objective routing** — Pareto front of (cost, time, risk) instead of single weight.
6. **PostgreSQL + PostGIS** for geospatial queries when scaling beyond 100 nodes.
7. **Authentication & role-based dashboards** — separate views for dispatcher / planner / executive.

---

## 17. Deliverables Checklist (final submission)

- [ ] Source code repo (`supply-chain-risk/`) with this folder structure.
- [ ] `DESIGN.md` (this file).
- [ ] `README.md` with one-command quickstart.
- [ ] `requirements.txt` pinned.
- [ ] `trained_models/delay_rf.joblib`.
- [ ] `data/processed/*.csv` (committed for reproducibility).
- [ ] `ml/evaluation_report.txt` (printed metrics).
- [ ] `tests/` with passing pytest run.
- [ ] Project report PDF (~15–20 pages) — sections mirror this design doc.
- [ ] Slide deck (~12 slides) — see section 14 for content.
- [ ] Demo video (optional but impressive) — 3-min screen recording.

---

## 18. Glossary (for your report)

- **Betweenness centrality** — how often a node lies on shortest paths between other pairs. High value = bridge.
- **Cascading failure** — when removing one node propagates damage through the network.
- **Edge weight** — numeric cost on a graph connection; here, distance × (1 + risk).
- **F1 score** — harmonic mean of precision and recall; balanced view of classifier quality.
- **NetworkX** — Python library for graph algorithms.
- **Streamlit** — Python framework that turns scripts into web apps.

---

*End of design playbook. Treat sections 7–12 as your week-by-week build script; treat 14–15 as your demo prep.*
