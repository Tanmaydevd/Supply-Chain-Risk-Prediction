"""Predict page — delay probability + live weather + live traffic + alternate route."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from app.components import risk_badge
from config import DATA_PROCESSED, WEATHER_MAP, TRAFFIC_MAP, TOMTOM_API_KEY
from services.prediction_service import predict_delay
from services.routing_service import best_route
from services.weather_service import get_weather
from services.traffic_service import get_traffic

st.set_page_config(page_title="Predict · SupplyGuard", page_icon="🔮", layout="wide")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from styles import inject; inject()
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#0d1117!important}
[data-testid="stSidebar"]{background:#111827!important}
.block-container{padding-top:1.2rem!important}
</style>""", unsafe_allow_html=True)

import streamlit.components.v1 as components
components.html("""
<style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700&display=swap');
*{font-family:'Inter',sans-serif;margin:0;padding:0}
.h{font-size:1.5rem;font-weight:700;color:#f9fafb;margin-bottom:4px}
.s{font-size:.85rem;color:#6b7280}
</style>
<div class="h">🔮 Delay Prediction</div>
<div class="s">AI-powered route risk · Live weather (Open-Meteo) · Live traffic (TomTom)</div>
""", height=60)

try:
    from ml.preprocess import get_node_names
except ImportError:
    get_node_names = None


def _load_node_names() -> list[str]:
    """Backward-compatible node loader if ml.preprocess API differs."""
    if callable(get_node_names):
        return get_node_names()
    df = pd.read_csv(DATA_PROCESSED / "nodes.csv")
    if "name" in df.columns:
        return df["name"].tolist()
    if "city" in df.columns:
        return df["city"].tolist()
    raise ValueError("nodes.csv must contain either 'name' or 'city' column")


nodes = _load_node_names()
edges = pd.read_csv(DATA_PROCESSED / "edges.csv")

# ── Route selectors ───────────────────────────────────────────────────────────
c1, c2 = st.columns(2)
origin = c1.selectbox("Origin warehouse / hub", nodes, index=nodes.index("Mumbai") if "Mumbai" in nodes else 0)
destination = c2.selectbox(
    "Destination",
    [c for c in nodes if c != origin],
    index=0,
)

# ── Live conditions panel ─────────────────────────────────────────────────────
st.divider()
col_fetch, col_status = st.columns([1, 3])

with col_fetch:
    fetch_clicked = st.button("🌐 Fetch Live Conditions", type="secondary", use_container_width=True)

# Store live results in session so they survive re-runs
if "live_weather"    not in st.session_state: st.session_state.live_weather  = None
if "live_traffic"    not in st.session_state: st.session_state.live_traffic  = None
if "weather_slider"  not in st.session_state: st.session_state.weather_slider = "Cloudy"
if "traffic_slider"  not in st.session_state: st.session_state.traffic_slider = "Medium"

if fetch_clicked:
    with st.spinner("Fetching weather and traffic..."):
        st.session_state.live_weather = get_weather(origin)
        st.session_state.live_traffic = get_traffic(origin, destination)
        # force sliders to update with live values
        _ws = {0: "Cloudy", 1: "Rain", 2: "Storm"}
        _ts = {0: "Low", 1: "Medium", 2: "High"}
        st.session_state["weather_slider"] = _ws.get(st.session_state.live_weather["score"], "Cloudy")
        st.session_state["traffic_slider"] = _ts.get(st.session_state.live_traffic["score"], "Medium")

lw = st.session_state.live_weather
lt = st.session_state.live_traffic

if lw or lt:
    with col_status:
        info_cols = st.columns(2)
        if lw:
            icon = {"Sunny/Cloudy": "☀️", "Rain": "🌧️", "Storm": "⛈️"}.get(lw["label"], "🌡️")
            info_cols[0].metric(
                f"{icon} Weather — {origin}",
                lw["label"],
                help=f"WMO code {lw['wmo_code']} | "
                     f"Precip: {lw['precipitation_mm']} mm | "
                     f"Wind: {lw['windspeed_kmh']} km/h",
            )
            if lw["error"]:
                info_cols[0].caption(f"⚠ {lw['error']}")

        if lt:
            t_icon = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(lt["label"], "🚦")
            src_label = "TomTom" if lt["source"] == "tomtom" else "Time estimate"
            detail = (
                f"{lt['current_speed_kmh']} / {lt['free_flow_speed_kmh']} km/h "
                f"(ratio {lt['congestion_ratio']})"
                if lt["source"] == "tomtom"
                else f"Source: {src_label}"
            )
            info_cols[1].metric(
                f"{t_icon} Traffic — {origin}→{destination}",
                lt["label"],
                help=detail,
            )
            if lt.get("error") and lt["source"] == "time_heuristic":
                info_cols[1].caption(
                    f"ℹ️ {lt['error']}" if "TOMTOM_API_KEY not set" in (lt["error"] or "")
                    else f"⚠ {lt['error']}"
                )

st.divider()

# ── Condition sliders (pre-filled from live data if available) ─────────────────
weather_options = list(WEATHER_MAP.keys())  # ["Sunny","Cloudy","Rain","Storm"]
traffic_options = list(TRAFFIC_MAP.keys())  # ["Low","Medium","High"]

_weather_score_to_label = {0: "Cloudy", 1: "Rain", 2: "Storm"}
_traffic_score_to_label = {0: "Low", 1: "Medium", 2: "High"}

col_w, col_t, col_l = st.columns(3)
weather = col_w.select_slider("Weather condition", options=weather_options,
                               key="weather_slider")
traffic = col_t.select_slider("Traffic level", options=traffic_options,
                               key="traffic_slider")
load = col_l.slider("Warehouse load (0=empty, 1=full)", 0.0, 1.0, 0.70, 0.05)

# ── Auto-detect transport mode from edge + node types ─────────────────────────
st.divider()

_nodes_df = pd.read_csv(DATA_PROCESSED / "nodes.csv")
_name_col  = "name" if "name" in _nodes_df.columns else "city"
_node_type = dict(zip(_nodes_df[_name_col], _nodes_df["type"]))

_direct_edge = edges[(edges.origin == origin) & (edges.destination == destination)]

if not _direct_edge.empty and "transport_mode" in _direct_edge.columns:
    # Ground truth: read from edge file
    mode_int  = int(_direct_edge.iloc[0]["transport_mode"])
    mode_src  = "edge data"
else:
    # No direct edge: infer from node types
    orig_type = _node_type.get(origin, "warehouse")
    dest_type = _node_type.get(destination, "warehouse")
    if orig_type == "port" or dest_type == "port":
        mode_int = 1   # sea
    elif orig_type == "airport" or dest_type == "airport":
        mode_int = 2   # air
    else:
        mode_int = 0   # road
    mode_src = "node types"

_MODE_INFO = {
    0: ("🚛 Road",  "#60a5fa", "Warehouse-to-warehouse direct road freight"),
    1: ("🚢 Sea",   "#34d399", "Port-to-port sea lane — includes vessel wait time"),
    2: ("✈️ Air",   "#f97316", "Airport-to-airport air cargo — includes flight status"),
}
mode_icon, mode_color, mode_desc = _MODE_INFO[mode_int]

import streamlit.components.v1 as _comp
_comp.html(f"""
<style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&display=swap');
*{{font-family:'Inter',sans-serif;margin:0;padding:0;box-sizing:border-box}}
.row{{display:flex;align-items:center;gap:10px;margin-bottom:4px}}
.badge{{background:{mode_color}22;border:1px solid {mode_color}55;color:{mode_color};
        font-size:.85rem;font-weight:600;padding:4px 14px;border-radius:99px}}
.desc{{color:#9ca3af;font-size:.8rem}} .src{{color:#6b7280;font-size:.72rem}}
</style>
<div class="row">
  <span class="badge">{mode_icon}</span>
  <span class="desc">{mode_desc}</span>
  <span class="src">(auto-detected from {mode_src})</span>
</div>
""", height=36)

# Live sea / air conditions
port_cong    = 0.2
vessel_delay = 0.0
flight_delay = 0.0

if mode_int == 1:   # Sea — fetch real port congestion
    from services.vessel_service import get_port_congestion, INDIAN_PORTS
    # Find nearest named port in our list to origin/destination
    _port_name = next(
        (p for p in INDIAN_PORTS if any(kw in origin for kw in p.split())),
        next((p for p in INDIAN_PORTS if any(kw in destination for kw in p.split())), "JNPT")
    )
    with st.spinner(f"Fetching live port congestion for {_port_name}..."):
        cong = get_port_congestion(_port_name)
    port_cong    = cong["congestion"]
    vessel_delay = cong["avg_wait_hrs"]
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Mode",         "🚢 Sea Freight")
    mc2.metric("Nearest port", _port_name)
    mc3.metric("Port congestion", f"{port_cong:.0%}",
               help=f"{cong['vessel_count']} vessels within 50 nm")
    mc4.metric("Est. vessel wait", f"{vessel_delay:.1f} hrs")

elif mode_int == 2:   # Air — fetch live flight data
    from services.flight_service import get_cargo_flights
    with st.spinner("Fetching live cargo flight data (OpenSky)..."):
        _flights = get_cargo_flights(timeout=5)
    _cargo_airborne  = [f for f in _flights if f["is_cargo"] and not f["on_ground"]]
    _cargo_grounded  = [f for f in _flights if f["is_cargo"] and f["on_ground"]]
    flight_delay = max(5.0, len(_cargo_grounded) * 2.5)   # grounded cargo → backlog
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Mode",             "✈️ Air Freight")
    mc2.metric("Live cargo flights", len(_cargo_airborne),
               help="Real ADS-B from OpenSky Network")
    mc3.metric("Grounded cargo a/c", len(_cargo_grounded),
               help="Aircraft on ground — potential loading delay")
    mc4.metric("Est. flight delay",  f"{flight_delay:.0f} min")

else:   # Road — use traffic already fetched via Fetch Live Conditions
    _lt = lt or get_traffic(origin, destination)

# ── Predict button ─────────────────────────────────────────────────────────────
if st.button("Predict Delay Risk", type="primary"):
    direct = edges[(edges.origin == origin) & (edges.destination == destination)]

    if direct.empty:
        # ── Find shortest path via Dijkstra ───────────────────────────────────
        try:
            alt = best_route(origin, destination)
        except FileNotFoundError:
            st.error("Model not trained yet. Run `python run_pipeline.py`.")
            st.stop()

        if not alt.get("path"):
            st.error("No path exists between these cities.")
            st.stop()

        path = alt["path"]
        st.info(f"No direct edge — shortest path via graph: **{' → '.join(path)}** ({alt['hops']} hops · {alt['total_distance_km']} km)")

        # ── Predict delay for each hop, then average ──────────────────────────
        hop_results = []
        for u, v in zip(path[:-1], path[1:]):
            hop_edge = edges[(edges.origin == u) & (edges.destination == v)]
            if not hop_edge.empty:
                he        = hop_edge.iloc[0]
                dist_km   = float(he.distance_km)
                hist_d    = float(he.hist_avg_delay_hrs)
                edge_mode = int(he["transport_mode"]) if "transport_mode" in he.index else mode_int
            else:
                dist_km   = round(alt["total_distance_km"] / alt["hops"], 1)
                hist_d    = 3.0
                edge_mode = mode_int

            r = predict_delay(
                distance_km        = dist_km,
                weather_score      = WEATHER_MAP[weather],
                traffic_score      = TRAFFIC_MAP[traffic],
                warehouse_load     = load,
                hist_avg_delay_hrs = hist_d,
                transport_mode     = edge_mode,
                port_congestion    = port_cong,
                vessel_delay_hrs   = vessel_delay,
                flight_delay_min   = flight_delay,
            )
            hop_results.append({
                "hop":   f"{u} → {v}",
                "prob":  r["delay_probability"],
                "score": r["risk_score"],
                "level": r["risk_level"],
                "dist":  dist_km,
                "hist":  hist_d,
            })

        # ── Average across all hops ───────────────────────────────────────────
        avg_prob  = round(sum(h["prob"]  for h in hop_results) / len(hop_results), 3)
        avg_score = int(  sum(h["score"] for h in hop_results) / len(hop_results))
        if avg_prob >= 0.66:
            avg_level = "High"
        elif avg_prob >= 0.33:
            avg_level = "Medium"
        else:
            avg_level = "Low"

        st.subheader(f"Route prediction: {origin} → {destination}")

        # ── Animated gauge (same as direct route) ────────────────────────────
        clr = "#ef4444" if avg_score >= 66 else "#f97316" if avg_score >= 33 else "#22c55e"
        components.html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700&display=swap');
*{{font-family:'Inter',sans-serif;box-sizing:border-box;margin:0;padding:0}}
.wrap{{display:flex;gap:20px;align-items:center;padding:6px 0}}
.gauge-box{{position:relative;width:160px;height:160px}}
svg{{transform:rotate(-90deg)}}
circle{{fill:none;stroke-width:14;stroke-linecap:round}}
.bg{{stroke:#1f2937}}
.arc{{stroke:{clr};stroke-dasharray:0 440;animation:fill .9s ease forwards}}
@keyframes fill{{to{{stroke-dasharray:{int(avg_score/100*440)} 440}}}}
.center{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center}}
.pct{{font-size:2rem;font-weight:700;color:{clr}}}
.lbl{{font-size:.75rem;color:#9ca3af;margin-top:2px}}
.stats{{display:grid;grid-template-columns:1fr 1fr;gap:12px;flex:1}}
.s-card{{background:#161b27;border:1px solid #1f2937;border-radius:10px;padding:14px}}
.s-lbl{{font-size:.72rem;color:#6b7280;text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px}}
.s-val{{font-size:1.4rem;font-weight:700;color:#f9fafb}}
</style>
<div class="wrap">
  <div class="gauge-box">
    <svg width="160" height="160" viewBox="0 0 160 160">
      <circle class="bg"  cx="80" cy="80" r="70"/>
      <circle class="arc" cx="80" cy="80" r="70"/>
    </svg>
    <div class="center"><div class="pct">{avg_score}</div><div class="lbl">avg risk score</div></div>
  </div>
  <div class="stats">
    <div class="s-card"><div class="s-lbl">Avg Delay Probability</div>
      <div class="s-val" style="color:{clr}">{avg_prob:.0%}</div></div>
    <div class="s-card"><div class="s-lbl">Overall Risk Level</div>
      <div class="s-val" style="color:{clr}">{avg_level}</div></div>
    <div class="s-card"><div class="s-lbl">Total Distance</div>
      <div class="s-val">{alt['total_distance_km']} km</div></div>
    <div class="s-card"><div class="s-lbl">Hops</div>
      <div class="s-val">{alt['hops']} stops</div></div>
  </div>
</div>
""", height=185)

        # ── Per-hop breakdown table ───────────────────────────────────────────
        st.markdown("**Per-hop breakdown**")
        hop_df = pd.DataFrame([{
            "Hop":              h["hop"],
            "Distance (km)":   h["dist"],
            "Delay Prob":      f"{h['prob']:.0%}",
            "Risk Score":      h["score"],
            "Risk Level":      h["level"],
            "Hist. Avg Delay": f"{h['hist']:.1f} hrs",
        } for h in hop_results])

        def _color_level(col):
            return [
                "color:#ef4444;font-weight:700" if v == "High"
                else "color:#f97316;font-weight:700" if v == "Medium"
                else "color:#22c55e;font-weight:700"
                for v in col
            ]
        st.dataframe(
            hop_df.style.apply(_color_level, subset=["Risk Level"]),
            use_container_width=True, hide_index=True
        )
        st.caption(f"Final prediction = average across {alt['hops']} hops  ·  Dijkstra shortest path by risk weight")
    else:
        e = direct.iloc[0]
        edge_mode = int(e.get("transport_mode", 0)) if "transport_mode" in e.index else mode_int
        try:
            r = predict_delay(
                distance_km=float(e.distance_km),
                weather_score=WEATHER_MAP[weather],
                traffic_score=TRAFFIC_MAP[traffic],
                warehouse_load=load,
                hist_avg_delay_hrs=float(e.hist_avg_delay_hrs),
                transport_mode=edge_mode,
                port_congestion=port_cong,
                vessel_delay_hrs=vessel_delay,
                flight_delay_min=flight_delay,
            )
        except FileNotFoundError:
            st.error("Model not trained yet. Run `python run_pipeline.py`.")
            st.stop()

        st.subheader(f"Direct route: {origin} -> {destination}")

        # ── animated risk gauge ──
        score = r["risk_score"]
        clr = "#ef4444" if score>=66 else "#f97316" if score>=33 else "#22c55e"
        lvl = r["risk_level"]
        components.html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700&display=swap');
*{{font-family:'Inter',sans-serif;box-sizing:border-box;margin:0;padding:0}}
.wrap{{display:flex;gap:20px;align-items:center;padding:6px 0}}
.gauge-box{{position:relative;width:160px;height:160px}}
svg{{transform:rotate(-90deg)}}
circle{{fill:none;stroke-width:14;stroke-linecap:round}}
.bg {{stroke:#1f2937}}
.arc{{stroke:{clr};stroke-dasharray:0 440;animation:fill .9s ease forwards}}
@keyframes fill{{to{{stroke-dasharray:{int(score/100*440)} 440}}}}
.center{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center}}
.pct{{font-size:2rem;font-weight:700;color:{clr}}}
.lbl{{font-size:.75rem;color:#9ca3af;margin-top:2px}}
.stats{{display:grid;grid-template-columns:1fr 1fr;gap:12px;flex:1}}
.s-card{{background:#161b27;border:1px solid #1f2937;border-radius:10px;padding:14px}}
.s-lbl{{font-size:.72rem;color:#6b7280;text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px}}
.s-val{{font-size:1.4rem;font-weight:700;color:#f9fafb}}
</style>
<div class="wrap">
  <div class="gauge-box">
    <svg width="160" height="160" viewBox="0 0 160 160">
      <circle class="bg"  cx="80" cy="80" r="70"/>
      <circle class="arc" cx="80" cy="80" r="70"/>
    </svg>
    <div class="center"><div class="pct">{score}</div><div class="lbl">risk score</div></div>
  </div>
  <div class="stats">
    <div class="s-card"><div class="s-lbl">Delay Probability</div>
      <div class="s-val" style="color:{clr}">{r['delay_probability']:.0%}</div></div>
    <div class="s-card"><div class="s-lbl">Risk Level</div>
      <div class="s-val" style="color:{clr}">{lvl}</div></div>
    <div class="s-card"><div class="s-lbl">Distance</div>
      <div class="s-val">{float(e.distance_km):.0f} km</div></div>
    <div class="s-card"><div class="s-lbl">Hist. Avg Delay</div>
      <div class="s-val">{float(e.hist_avg_delay_hrs):.1f} hrs</div></div>
  </div>
</div>
""", height=185)

        data_src = []
        if lw and lw["error"] is None:
            data_src.append(f"Weather: Open-Meteo live ({lw['label']})")
        if lt and lt["source"] == "tomtom":
            data_src.append(f"Traffic: TomTom live ({lt['label']})")
        elif lt:
            data_src.append(f"Traffic: time-heuristic ({lt['label']})")

        st.caption(
            f"Distance: {float(e.distance_km):.0f} km  ·  "
            f"Hist. avg delay: {float(e.hist_avg_delay_hrs):.1f} hrs"
            + ("  ·  " + " | ".join(data_src) if data_src else "")
        )

        if r["delay_probability"] >= 0.60:
            st.warning(f"Delay probability {r['delay_probability']:.0%} exceeds 60% — searching for a safer alternate route...")
            alt = best_route(origin, destination)
            if alt.get("path") and len(alt["path"]) > 2:
                alt_path_str = " → ".join(alt["path"])
                risk_saved   = round(r["delay_probability"] - (alt["total_risk"] / max(alt["hops"],1)), 3)
                components.html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700&display=swap');
*{{font-family:'Inter',sans-serif;margin:0;padding:0;box-sizing:border-box}}
.box{{background:#0f3326;border:1px solid #166534;border-radius:12px;padding:14px 18px}}
.top{{display:flex;align-items:center;gap:8px;margin-bottom:10px}}
.icon{{font-size:1.1rem}}.ttl{{font-size:.9rem;font-weight:700;color:#4ade80}}
.path{{font-size:.95rem;color:#f9fafb;font-weight:600;letter-spacing:-.01em;margin-bottom:10px;
       word-break:break-word}}
.chips{{display:flex;gap:8px;flex-wrap:wrap}}
.chip{{font-size:.72rem;font-weight:600;padding:3px 10px;border-radius:99px;
       background:#14532d;border:1px solid #166534;color:#86efac}}
.chip2{{background:#1c1007;border:1px solid #92400e;color:#fbbf24}}
</style>
<div class="box">
  <div class="top"><span class="icon">🔀</span>
    <span class="ttl">Recommended Alternate Route (Dijkstra)</span></div>
  <div class="path">{alt_path_str}</div>
  <div class="chips">
    <span class="chip">✓ {alt['hops']} hops</span>
    <span class="chip">📏 {alt['total_distance_km']} km</span>
    <span class="chip">⚡ Risk {alt['total_risk']:.3f}</span>
    <span class="chip2">Direct risk {r['delay_probability']:.0%}</span>
  </div>
</div>
""", height=130)
            elif alt.get("path"):
                st.info("Direct path is already the lowest-risk option in the network. Consider adjusting departure window.")
            else:
                st.error("No alternate path found in the network.")
        else:
            st.success(f"Risk is acceptable on the direct route ({r['delay_probability']:.0%} delay probability).")

# ── TomTom key setup hint (shown once, only when key not set) ─────────────────
if not TOMTOM_API_KEY:
    with st.expander("ℹ️ Enable real-time traffic (TomTom API key setup)"):
        st.markdown("""
**To get live traffic instead of the time-of-day estimate:**

1. Register free at [developer.tomtom.com](https://developer.tomtom.com/user/register) (2,500 req/day free)
2. Copy your API key
3. Set the environment variable before launching Streamlit:

```powershell
# PowerShell
$env:TOMTOM_API_KEY = "paste_your_key_here"
streamlit run app/Home.py
```

```cmd
:: CMD
set TOMTOM_API_KEY=paste_your_key_here
streamlit run app/Home.py
```

Weather data (Open-Meteo) is already live — no key needed.
        """)
