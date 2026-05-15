"""Live Map — warehouses, ports, airports, cargo flights, vessels, risk edges."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import folium
import streamlit as st
from streamlit_folium import st_folium
import pandas as pd

from graph.graph_builder import build_graph, annotate_with_risk
import sys as _sys; _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from styles import inject
inject()
from services.flight_service import get_cargo_flights
from services.vessel_service import get_vessels_near_india

st.set_page_config(page_title="Live Map", page_icon="🗺️", layout="wide")
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#0d1117!important}
[data-testid="stSidebar"]{background:#111827!important}
.block-container{padding-top:1rem!important}
</style>""", unsafe_allow_html=True)

st.markdown("""
<h2 style='color:#f9fafb;margin-bottom:4px'>🗺️ Live India Logistics Map</h2>
<p style='color:#6b7280;font-size:.87rem;margin-bottom:12px'>
Warehouses · Ports · Airports · Real cargo flights (OpenSky) · Vessels (AIS) · ML-predicted delay risk
</p>""", unsafe_allow_html=True)

# ── controls ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
show_warehouses = c1.toggle("🏭 Warehouses",  value=True)
show_ports      = c2.toggle("⚓ Ports",        value=True)
show_airports   = c3.toggle("✈️ Airports",     value=True)
show_flights    = c4.toggle("🛩 Live Flights", value=True)
show_vessels    = c5.toggle("🚢 Live Vessels", value=True)

edge_filter = st.select_slider(
    "Show edges by mode",
    options=["All", "Road only", "Sea only", "Air only"],
    value="All",
)
risk_filter = st.select_slider(
    "Minimum risk to show edge",
    options=["All", ">20%", ">40%", ">60%"],
    value="All",
)

# ── load data ─────────────────────────────────────────────────────────────────
@st.cache_resource(ttl=120)
def _graph():
    return annotate_with_risk(build_graph())

@st.cache_data(ttl=60)
def _flights():
    return get_cargo_flights()

@st.cache_data(ttl=120)
def _vessels():
    return get_vessels_near_india()

try:
    G = _graph()
    graph_ok = True
except FileNotFoundError:
    graph_ok = False
    st.error("Run `python run_pipeline.py` first.")
    st.stop()

flights = _flights() if show_flights else []
vessels = _vessels() if show_vessels else []

# ── build folium map ──────────────────────────────────────────────────────────
m = folium.Map(location=[20.5, 79.0], zoom_start=5,
               tiles="CartoDB dark_matter", prefer_canvas=True)

def _risk_color(r):
    return "#22c55e" if r < 0.33 else "#f97316" if r < 0.66 else "#ef4444"

# ── edges ─────────────────────────────────────────────────────────────────────
MODE_LABELS = {0: "road", 1: "sea", 2: "air"}
MODE_STYLE  = {
    0: {"color": "#60a5fa", "dash": None,  "weight": 1.5},   # road  blue
    1: {"color": "#34d399", "dash": "8,6", "weight": 2.0},   # sea   green dashed
    2: {"color": "#f97316", "dash": "4,4", "weight": 1.5},   # air   orange dotted
}

risk_thresh = {"All": 0.0, ">20%": 0.20, ">40%": 0.40, ">60%": 0.60}[risk_filter]
mode_filter = {"All": None, "Road only": 0, "Sea only": 1, "Air only": 2}.get(edge_filter)

for u, v, d in G.edges(data=True):
    mode = int(d.get("transport_mode", 0))
    risk = d.get("risk", 0.3)
    if mode_filter is not None and mode != mode_filter:
        continue
    if risk < risk_thresh:
        continue
    a, b = G.nodes[u], G.nodes[v]
    sty = MODE_STYLE[mode]
    line = folium.PolyLine(
        [(a["lat"], a["lon"]), (b["lat"], b["lon"])],
        color=_risk_color(risk),
        weight=sty["weight"], opacity=0.65,
        tooltip=f"{u}→{v} | {MODE_LABELS[mode]} | risk {risk:.0%}",
        dash_array=sty["dash"],
    )
    line.add_to(m)

# ── node icons ────────────────────────────────────────────────────────────────
ICON_MAP = {
    "warehouse": ("🏭", "#60a5fa", 8),
    "port":      ("⚓", "#34d399", 10),
    "airport":   ("✈️", "#f97316", 9),
    "hub":       ("🔵", "#a78bfa", 8),
}

for n, d in G.nodes(data=True):
    ntype = d.get("type", "warehouse")
    if ntype == "warehouse" and not show_warehouses: continue
    if ntype == "port"      and not show_ports:      continue
    if ntype == "airport"   and not show_airports:   continue

    emoji, color, radius = ICON_MAP.get(ntype, ("🔵", "#9ca3af", 7))
    folium.CircleMarker(
        [d["lat"], d["lon"]], radius=radius,
        color=color, fill=True, fill_color=color, fill_opacity=0.85,
        tooltip=f"{emoji} {n} ({ntype})",
        popup=folium.Popup(
            f"<b>{n}</b><br>Type: {ntype}<br>"
            f"Subtype: {d.get('subtype','')}",
            max_width=200,
        ),
    ).add_to(m)

# ── live cargo flights ────────────────────────────────────────────────────────
if show_flights and flights:
    cargo_only = [f for f in flights if f["is_cargo"]]
    all_shown  = cargo_only if cargo_only else flights[:80]

    for f in all_shown:
        color = "#ef4444" if f["is_cargo"] else "#6b7280"
        folium.CircleMarker(
            [f["lat"], f["lon"]], radius=4,
            color=color, fill=True, fill_color=color, fill_opacity=0.9,
            tooltip=(
                f"✈ {f['callsign']} ({f['origin_country']})<br>"
                f"Alt: {f['altitude_m']:.0f}m · {f['velocity_kmh']:.0f}km/h · "
                f"{'CARGO' if f['is_cargo'] else 'passenger'}"
            ),
        ).add_to(m)

# ── live vessels ──────────────────────────────────────────────────────────────
if show_vessels and vessels:
    for v in vessels:
        risk_c = _risk_color(v["delay_risk"])
        folium.RegularPolygonMarker(
            [v["lat"], v["lon"]], number_of_sides=3,
            radius=6, rotation=v.get("heading", 0),
            color=risk_c, fill=True, fill_color=risk_c, fill_opacity=0.85,
            tooltip=(
                f"🚢 {v['name']} ({v['flag']})<br>"
                f"{v['vessel_type']} · {v['cargo']}<br>"
                f"Speed: {v['speed_knots']} kn · Status: {v['status']}<br>"
                f"Nearest port: {v['nearest_port']}<br>"
                f"Delay risk: {v['delay_risk']:.0%} · {v['source']}"
            ),
        ).add_to(m)

st_folium(m, width=None, height=600, key="live-map")

# ── legend ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='display:flex;gap:20px;flex-wrap:wrap;font-size:.8rem;color:#9ca3af;margin-top:6px'>
  <span>🏭 Warehouse</span><span>⚓ Seaport</span><span>✈️ Cargo Airport</span>
  <span>🔴 Cargo flight (live)</span><span>▲ Vessel (live)</span>
  <span style='color:#60a5fa'>━ Road</span>
  <span style='color:#34d399'>╌ Sea lane</span>
  <span style='color:#f97316'>┄ Air route</span>
  <span style='color:#22c55e'>■ Low risk</span>
  <span style='color:#f97316'>■ Medium</span>
  <span style='color:#ef4444'>■ High risk</span>
</div>""", unsafe_allow_html=True)

# ── live stats ────────────────────────────────────────────────────────────────
st.divider()
col1, col2, col3, col4, col5 = st.columns(5)
cargo_cnt = len([f for f in flights if f["is_cargo"]])
col1.metric("Warehouses", sum(1 for _,d in G.nodes(data=True) if d.get("type")=="warehouse"))
col2.metric("Seaports",   sum(1 for _,d in G.nodes(data=True) if d.get("type")=="port"))
col3.metric("Airports",   sum(1 for _,d in G.nodes(data=True) if d.get("type")=="airport"))
col4.metric("Live cargo flights", cargo_cnt, help="Real ADS-B data from OpenSky Network")
col5.metric("Live vessels",       len(vessels), help="AIS vessel positions near Indian ports")

# ── live flights table ────────────────────────────────────────────────────────
if show_flights and flights:
    with st.expander(f"Live cargo flights over India ({cargo_cnt})", expanded=False):
        cargo_df = pd.DataFrame([
            {"Callsign": f["callsign"], "Country": f["origin_country"],
             "Alt (m)": int(f["altitude_m"]), "Speed (km/h)": f["velocity_kmh"],
             "Heading": f["heading"],
             "Status": "On Ground" if f["on_ground"] else "Airborne",
             "Cargo": "Yes" if f["is_cargo"] else "No"}
            for f in flights if f["is_cargo"]
        ])
        st.dataframe(cargo_df, use_container_width=True, hide_index=True, height=300)

# ── vessels table ─────────────────────────────────────────────────────────────
if show_vessels and vessels:
    with st.expander(f"Vessels near Indian ports ({len(vessels)})", expanded=False):
        v_df = pd.DataFrame([
            {"Name": v["name"], "Type": v["vessel_type"], "Flag": v["flag"],
             "Speed (kn)": v["speed_knots"], "Status": v["status"],
             "Cargo": v["cargo"], "Nearest Port": v["nearest_port"],
             "Delay Risk": f"{v['delay_risk']:.0%}", "Source": v["source"]}
            for v in vessels
        ])

        def _style_risk(col):
            return ["color:#ef4444;font-weight:700" if float(v.strip("%"))/100 >= 0.5
                    else "color:#fde68a;font-weight:700" if float(v.strip("%"))/100 >= 0.3
                    else "color:#86efac" for v in col]

        st.dataframe(v_df.style.apply(_style_risk, subset=["Delay Risk"]),
                     use_container_width=True, hide_index=True, height=300)
