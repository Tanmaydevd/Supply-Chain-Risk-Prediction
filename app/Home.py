"""SupplyGuard — AI Risk Dashboard (Streamlit + animated HTML components)."""
from __future__ import annotations
import sys, random, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import folium
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

from services.graph_service import get_annotated_graph, overview_metrics
from services.weather_service import get_weather

st.set_page_config(page_title="SupplyGuard", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="expanded")

# ── global CSS injection ───────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [data-testid="stAppViewContainer"] {
    background: #0d1117 !important;
    font-family: 'Inter', sans-serif;
}
[data-testid="stSidebar"]  { background: #111827 !important; }
[data-testid="stHeader"]   { background: transparent !important; }
.block-container           { padding-top: 1rem !important; padding-bottom: 2rem !important; }
section[data-testid="stSidebar"] > div { padding-top: 1rem; }
[data-testid="stSidebarNavLink"] { font-size: 0.9rem; }
hr                         { border-color: #1f2937 !important; }
</style>
""", unsafe_allow_html=True)

# ── load data ─────────────────────────────────────────────────────────────────
@st.cache_resource(ttl=60)
def _graph():
    return get_annotated_graph(), overview_metrics()

try:
    G, m_data = _graph()
    graph_ok = True
except FileNotFoundError:
    graph_ok, G, m_data = False, None, {"n_nodes":15,"n_edges":36,"avg_risk":0,"n_critical":5}

# ── live weather threats ───────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def _threats():
    from services.vessel_service import get_port_congestion
    from services.flight_service import get_cargo_flights

    results = []
    # Weather threats
    for city in ["Mumbai","Delhi","Chennai","Kolkata","Bangalore"]:
        w = get_weather(city)
        if w["score"] >= 1:
            results.append({"title":"Storm Alert" if w["score"]==2 else "Rain / Low Visibility",
                "loc":f"{city} Hub","sev":"Critical" if w["score"]==2 else "Medium",
                "orders":random.randint(6,40),"action":"Rerouted" if w["score"]==2 else "Delayed",
                "detail":f"{w['precipitation_mm']}mm · {w['windspeed_kmh']}km/h"})
    # Port congestion threats
    for port in ["JNPT","Chennai","Visakhapatnam"]:
        c = get_port_congestion(port)
        if c["congestion"] > 0.6:
            results.append({"title":"Port Congestion","loc":f"{port} Port",
                "sev":"High" if c["congestion"]>0.75 else "Medium",
                "orders":c["vessel_count"]*3,
                "action":"Delayed","detail":f"{c['vessel_count']} vessels · wait {c['avg_wait_hrs']:.0f}h"})
    # Flight threats
    try:
        flights = get_cargo_flights(timeout=4)
        on_ground = [f for f in flights if f["is_cargo"] and f["on_ground"]]
        if len(on_ground) > 5:
            results.append({"title":"Airport Cargo Backlog","loc":"Multiple Airports",
                "sev":"Medium","orders":len(on_ground)*2,
                "action":"Delayed","detail":f"{len(on_ground)} cargo aircraft on ground"})
    except Exception:
        pass
    results.append({"title":"Labour Strike","loc":"Mumbai Port","sev":"High",
        "orders":12,"action":"Rerouted","detail":"Dock workers industrial action"})
    return results

threats = _threats()

# ── KPIs ──────────────────────────────────────────────────────────────────────
from services.flight_service import get_cargo_flights as _get_flights
from services.vessel_service import get_vessels_near_india as _get_vessels

@st.cache_data(ttl=60)
def _live_assets():
    try:
        flights = _get_flights(timeout=5)
        vessels = _get_vessels()
        cargo_flights = len([f for f in flights if f["is_cargo"]])
        return cargo_flights, len(vessels)
    except Exception:
        return 0, 0

all_risks      = [d["risk"] for _,_,d in G.edges(data=True)] if graph_ok else []
routes_at_risk = sum(1 for r in all_risks if r >= 0.5)
total_active   = max(m_data["n_edges"]*34, 1200)
ships_at_risk  = routes_at_risk * 31
fin_exp        = round(ships_at_risk * 22000 / 1e6, 1)
ai_threats     = len(threats)
avg_risk       = m_data["avg_risk"]
live_flights, live_vessels = _live_assets()

# ── HEADER ────────────────────────────────────────────────────────────────────
components.html(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  * {{ font-family: 'Inter', sans-serif; box-sizing: border-box; margin:0; padding:0; }}
  .header {{ display:flex; justify-content:space-between; align-items:center; padding:4px 0 16px; }}
  .title  {{ font-size:1.6rem; font-weight:700; color:#f9fafb; }}
  .sub    {{ font-size:.85rem; color:#6b7280; margin-top:2px; }}
  .live   {{ display:flex; align-items:center; gap:6px; background:#14532d; border:1px solid #166534;
             color:#86efac; font-size:.75rem; font-weight:600; padding:5px 12px; border-radius:99px; }}
  .dot    {{ width:8px; height:8px; border-radius:50%; background:#4ade80;
             animation: pulse 2s ease-in-out infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1;transform:scale(1)}} 50%{{opacity:.5;transform:scale(1.3)}} }}
</style>
<div class="header">
  <div>
    <div class="title">🛡️ AI Risk Prediction Overview</div>
    <div class="sub">Live monitoring of India logistics infrastructure · Open-Meteo weather · TomTom traffic</div>
  </div>
  <div class="live"><div class="dot"></div>Live · {'Alert' if ai_threats>2 else 'Secure'}</div>
</div>
""", height=80)

# ── ANIMATED KPI CARDS (6 cards: shipments + risk + threats + finance + flights + vessels) ──
components.html(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  * {{ font-family:'Inter',sans-serif; box-sizing:border-box; margin:0; padding:0; }}
  .grid {{ display:grid; grid-template-columns:repeat(6,1fr); gap:10px; }}
  .card {{ background:#161b27; border:1px solid #1f2937; border-radius:12px; padding:16px 16px;
           animation: slideUp .5s ease forwards; opacity:0; }}
  .card:nth-child(1){{animation-delay:.05s}} .card:nth-child(2){{animation-delay:.10s}}
  .card:nth-child(3){{animation-delay:.15s}} .card:nth-child(4){{animation-delay:.20s}}
  .card:nth-child(5){{animation-delay:.25s}} .card:nth-child(6){{animation-delay:.30s}}
  @keyframes slideUp {{ from{{opacity:0;transform:translateY(16px)}} to{{opacity:1;transform:translateY(0)}} }}
  .label {{ font-size:.65rem; color:#6b7280; font-weight:600; text-transform:uppercase;
            letter-spacing:.07em; margin-bottom:8px; }}
  .value {{ font-size:1.75rem; font-weight:700; }}
  .icon  {{ font-size:1rem; float:right; opacity:.6; }}
  .c-white{{color:#f9fafb}} .c-red{{color:#ef4444}} .c-orange{{color:#f97316}}
  .c-blue{{color:#60a5fa}} .c-green{{color:#34d399}}
</style>
<div class="grid">
  <div class="card">
    <div class="label">Active Shipments <span class="icon">📦</span></div>
    <div class="value c-white" id="v1">0</div>
  </div>
  <div class="card">
    <div class="label">Shipments at Risk <span class="icon">⚠️</span></div>
    <div class="value c-red" id="v2">0</div>
  </div>
  <div class="card">
    <div class="label">AI Threats <span class="icon">🛡️</span></div>
    <div class="value c-orange" id="v3">0</div>
  </div>
  <div class="card">
    <div class="label">Financial Exposure <span class="icon">💰</span></div>
    <div class="value c-white" id="v4">₹0M</div>
  </div>
  <div class="card">
    <div class="label">Cargo Flights Live <span class="icon">✈️</span></div>
    <div class="value c-blue" id="v5">0</div>
  </div>
  <div class="card">
    <div class="label">Vessels Tracked <span class="icon">🚢</span></div>
    <div class="value c-green" id="v6">0</div>
  </div>
</div>
<script>
function animCount(id,target,prefix,suffix,dur){{
  var el=document.getElementById(id),start=0,steps=50,inc=target/steps,iv=dur/steps;
  var t=setInterval(function(){{start+=inc;if(start>=target){{start=target;clearInterval(t);}}
    el.textContent=prefix+Math.round(start).toLocaleString()+suffix;}},iv);
}}
animCount('v1',{total_active},'','',800);
animCount('v2',{ships_at_risk},'','',900);
animCount('v3',{ai_threats},'','',600);
animCount('v4',{fin_exp},'₹','M',700);
animCount('v5',{live_flights},'','',1000);
animCount('v6',{live_vessels},'','',1100);
</script>
""", height=115)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── MAP + THREAT FEED ─────────────────────────────────────────────────────────
map_col, feed_col = st.columns([7, 3])

with map_col:
    components.html("""
    <div style="font-family:Inter,sans-serif;font-size:.75rem;font-weight:600;color:#6b7280;
                text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">
      🗺 India Logistics Network
    </div>""", height=28)

    if graph_ok:
        fm = folium.Map(location=[22,80], zoom_start=5, tiles="CartoDB dark_matter")
        for n,d in G.nodes(data=True):
            folium.CircleMarker([d["lat"],d["lon"]], radius=7,
                popup=f"{n} ({d.get('type','')})",
                color="#60a5fa", fill=True, fill_color="#60a5fa", fill_opacity=0.9).add_to(fm)
        for u,v,d in G.edges(data=True):
            a,b = G.nodes[u], G.nodes[v]
            c = "#22c55e" if d["risk"]<.33 else "#f97316" if d["risk"]<.66 else "#ef4444"
            folium.PolyLine([(a["lat"],a["lon"]),(b["lat"],b["lon"])],
                color=c, weight=2.5, opacity=.8,
                tooltip=f"{u}→{v} {d['risk']:.0%} delay risk").add_to(fm)
        st_folium(fm, width=None, height=400, key="home-map")
    else:
        st.warning("Run `python run_pipeline.py` first.")

with feed_col:
    # threat cards as animated HTML
    SEV_COLORS = {"Critical":("#7f1d1d","#fca5a5","#991b1b"),
                  "High":("#7c2d12","#fdba74","#9a3412"),
                  "Medium":("#78350f","#fde68a","#92400e"),
                  "Low":("#14532d","#86efac","#166534")}
    ACT_CLR    = {"Rerouted":"#a78bfa","Delayed":"#fca5a5","At Risk":"#fcd34d"}

    cards_html = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    *{font-family:'Inter',sans-serif;box-sizing:border-box;margin:0;padding:0}
    .sec{font-size:.72rem;font-weight:600;color:#6b7280;text-transform:uppercase;
         letter-spacing:.08em;margin-bottom:8px}
    .tc{border:1px solid #1f2937;border-radius:9px;padding:12px 14px;margin-bottom:8px;
        animation:fadeIn .4s ease forwards;opacity:0}
    @keyframes fadeIn{from{opacity:0;transform:translateX(12px)}to{opacity:1;transform:translateX(0)}}
    .row{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px}
    .tt{font-size:.9rem;font-weight:600;color:#e5e7eb}
    .bdg{font-size:.65rem;font-weight:700;padding:2px 7px;border-radius:4px;text-transform:uppercase}
    .loc{font-size:.75rem;color:#9ca3af;margin:3px 0 4px}
    .det{font-size:.72rem;color:#6b7280;margin-bottom:6px}
    .meta{display:flex;justify-content:space-between}
    .orders{color:#9ca3af;font-size:.75rem}
    .nh{border:1px solid #1f2937;border-radius:9px;padding:12px 14px;margin-top:6px}
    .nh-title{font-size:.7rem;font-weight:600;color:#6b7280;text-transform:uppercase;
              letter-spacing:.07em;margin-bottom:8px}
    .nh-row{display:flex;justify-content:space-between;margin-bottom:5px;font-size:.82rem}
    .nh-lbl{color:#9ca3af} .nh-val{font-weight:600;color:#f9fafb}
    </style>
    <div class="sec">⚠ Live AI Threat Feed</div>
    """
    for i, t in enumerate(threats):
        bg, fg, bdr = SEV_COLORS.get(t["sev"], SEV_COLORS["Medium"])
        ac = ACT_CLR.get(t["action"], "#9ca3af")
        delay = i * 0.12
        cards_html += f"""
        <div class="tc" style="background:{bg}22;border-color:{bdr};animation-delay:{delay}s">
          <div class="row">
            <span class="tt">{t['title']}</span>
            <span class="bdg" style="background:{bg};color:{fg}">{t['sev']}</span>
          </div>
          <div class="loc">📍 {t['loc']}</div>
          <div class="det">{t['detail']}</div>
          <div class="meta">
            <span class="orders">🚚 {t['orders']} orders</span>
            <span style="color:{ac};font-size:.75rem;font-weight:600">{t['action']}</span>
          </div>
        </div>"""

    # Network health
    rc = "#22c55e" if avg_risk<.33 else "#f97316" if avg_risk<.66 else "#ef4444"
    cards_html += f"""
    <div class="nh">
      <div class="nh-title">Network Health</div>
      <div class="nh-row"><span class="nh-lbl">Cities online</span><span class="nh-val">{m_data['n_nodes']}</span></div>
      <div class="nh-row"><span class="nh-lbl">Active routes</span><span class="nh-val">{m_data['n_edges']}</span></div>
      <div class="nh-row">
        <span class="nh-lbl">Avg delay risk</span>
        <span style="color:{rc};font-weight:700">{avg_risk:.0%}</span>
      </div>
    </div>"""

    components.html(cards_html, height=460, scrolling=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── ACTIVE SHIPMENTS TABLE ────────────────────────────────────────────────────
import pandas as pd

PRODUCTS = ["Electronics","Automotive Parts","Pharmaceuticals","Textiles & Apparel",
            "Industrial Machinery","FMCG","Semiconductors","Cold Chain / Food",
            "Chemicals","Steel & Metals"]

def _status(r):
    if r>=.70: return "🟣 Rerouted"
    if r>=.55: return "🔴 Delayed"
    if r>=.33: return "🟡 At Risk"
    return "🟢 In Transit"

random.seed(42)
today = datetime.date.today()
rows = []
if graph_ok:
    for i,(u,v,d) in enumerate(sorted(G.edges(data=True),key=lambda x:-x[2]["risk"])[:10]):
        eta = today + datetime.timedelta(days=random.randint(2,14))
        rows.append({"Order ID":f"ORD-{8821+i}",
                     "Product":PRODUCTS[i%len(PRODUCTS)],
                     "Source":f"{u}, IN", "Destination":f"{v}, IN",
                     "Status":_status(d["risk"]),
                     "Delay Risk":f"{d['risk']:.0%}",
                     "Carrier":random.choice(["Delhivery","DTDC","Blue Dart","Ekart","Xpressbees"]),
                     "ETA":eta.strftime("%b %d, %Y")})

# section header
components.html("""
<style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600&display=swap');
*{font-family:'Inter',sans-serif;margin:0;padding:0}
.s{font-size:.75rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.08em}
</style><div class="s">📦 Active Shipments</div>""", height=24)

if rows:
    df = pd.DataFrame(rows)

    def _style_status(col):
        return ["color:#a78bfa;font-weight:600" if "Rerouted" in v
                else "color:#fca5a5;font-weight:600" if "Delayed" in v
                else "color:#fde68a;font-weight:600" if "At Risk" in v
                else "color:#86efac;font-weight:600" for v in col]

    def _style_risk(col):
        out = []
        for v in col:
            p = float(v.strip("%"))/100
            out.append("color:#fca5a5;font-weight:700" if p>=.70
                        else "color:#fde68a;font-weight:700" if p>=.50
                        else "color:#86efac")
        return out

    styled = df.style.apply(_style_status, subset=["Status"]).apply(_style_risk, subset=["Delay Risk"])
    st.dataframe(styled, use_container_width=True, hide_index=True, height=380)
else:
    st.info("Run pipeline to load shipment data.")

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ── QUICK NAV ─────────────────────────────────────────────────────────────────
components.html("""
<style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600&display=swap');
*{font-family:'Inter',sans-serif;margin:0;padding:0}
.s{font-size:.75rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.08em}
</style><div class="s">Quick Actions</div>""", height=24)

n1,n2,n3,n4 = st.columns(4)
n1.page_link("pages/1_Predict.py",   label="🔮 Predict Delay",    use_container_width=True)
n2.page_link("pages/2_Map.py",       label="🗺 Network Map",       use_container_width=True)
n3.page_link("pages/3_Simulate.py",  label="💥 Simulate Failure",  use_container_width=True)
n4.page_link("pages/4_Analytics.py", label="📊 Analytics",         use_container_width=True)
