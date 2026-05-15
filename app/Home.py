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
@st.cache_data(ttl=600)
def _threats():
    from services.vessel_service import get_port_congestion, get_vessels_near_india
    from services.flight_service import get_cargo_flights
    from services.news_service   import get_disruption_news
    from concurrent.futures      import ThreadPoolExecutor, as_completed

    # ── Fetch all data sources in parallel ────────────────────────────────────
    def _weather_all():
        return {c: get_weather(c) for c in ["Mumbai","Delhi","Chennai","Kolkata","Bangalore"]}

    def _vessels_all():
        # fetch once, then derive all 3 ports from single call
        get_vessels_near_india(timeout=5)
        return {p: get_port_congestion(p) for p in ["JNPT","Chennai","Visakhapatnam"]}

    def _flights():
        try:    return get_cargo_flights(timeout=4)
        except: return []

    def _news():
        try:    return get_disruption_news(max_results=3)
        except: return []

    with ThreadPoolExecutor(max_workers=4) as pool:
        fw = pool.submit(_weather_all)
        fv = pool.submit(_vessels_all)
        ff = pool.submit(_flights)
        fn = pool.submit(_news)
        weather_data  = fw.result()
        port_data     = fv.result()
        flight_data   = ff.result()
        news_data     = fn.result()

    results = []

    # ── Weather ───────────────────────────────────────────────────────────────
    for city, w in weather_data.items():
        if w["score"] == 2:
            title, sev, action = "Storm Alert",           "Critical", "Reroute advised"
        elif w["score"] == 1:
            title, sev, action = "Rain / Low Visibility", "Medium",   "Monitor"
        else:
            title, sev, action = "Clear Conditions",      "Low",      "On schedule"
        results.append({
            "title":  title, "loc": f"{city} Hub", "sev": sev,
            "orders": "—",   "action": action,
            "detail": f"{w['precipitation_mm']}mm · {w['windspeed_kmh']}km/h",
        })

    # ── Port congestion ───────────────────────────────────────────────────────
    for port, c in port_data.items():
        if c["congestion"] > 0.75:   sev, action = "High",   "Delayed"
        elif c["congestion"] > 0.4:  sev, action = "Medium", "Monitor"
        else:                        sev, action = "Low",     "Normal"
        results.append({
            "title":  "Port Congestion" if c["congestion"] > 0.4 else "Port Clear",
            "loc":    f"{port} Port", "sev": sev,
            "orders": f"{c['vessel_count']} vessels", "action": action,
            "detail": f"{c['vessel_count']} vessels within 50nm · wait ~{c['avg_wait_hrs']:.0f}h",
        })

    # ── Cargo flights ─────────────────────────────────────────────────────────
    if flight_data:
        airborne  = [f for f in flight_data if f["is_cargo"] and not f["on_ground"]]
        on_ground = [f for f in flight_data if f["is_cargo"] and f["on_ground"]]
        sev    = "Medium" if len(on_ground) > 5 else "Low"
        title  = "Airport Cargo Backlog" if len(on_ground) > 5 else "Cargo Flights Normal"
        action = "Delayed" if len(on_ground) > 5 else "On schedule"
        results.append({
            "title":  title, "loc": "Indian Airspace", "sev": sev,
            "orders": f"{len(airborne)} airborne",     "action": action,
            "detail": f"{len(airborne)} airborne · {len(on_ground)} on ground (OpenSky live)",
        })

    # ── News alerts ───────────────────────────────────────────────────────────
    for article in news_data:
        results.append({
            "title":  article["title"],  "loc":    article["loc"],
            "sev":    article["sev"],    "orders": article.get("time","—"),
            "action": article["action"], "detail": article["detail"],
        })

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
network_routes = m_data["n_edges"]           # real — graph edge count
high_risk_routes = routes_at_risk            # real — edges with risk >= 0.5
avg_risk_pct   = round(m_data["avg_risk"] * 100, 1)  # real — mean edge risk %
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
    <div class="label">Network Routes <span class="icon">🗺</span></div>
    <div class="value c-white" id="v1">0</div>
  </div>
  <div class="card">
    <div class="label">High Risk Routes <span class="icon">⚠️</span></div>
    <div class="value c-red" id="v2">0</div>
  </div>
  <div class="card">
    <div class="label">AI Threats <span class="icon">🛡</span></div>
    <div class="value c-orange" id="v3">0</div>
  </div>
  <div class="card">
    <div class="label">Avg Network Risk <span class="icon">📊</span></div>
    <div class="value c-white" id="v4">0%</div>
  </div>
  <div class="card">
    <div class="label">Cargo Flights Live <span class="icon">✈</span></div>
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
animCount('v1',{network_routes},'','',800);
animCount('v2',{high_risk_routes},'','',900);
animCount('v3',{ai_threats},'','',600);
animCount('v4',{avg_risk_pct},'','%',700);
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

# ── ACTIVE SHIPMENTS TABLE (AfterShip live) ───────────────────────────────────
import pandas as pd
from services.aftership_service import get_all_trackings

@st.cache_data(ttl=600)
def _load_shipments():
    return get_all_trackings(limit=20)

components.html("""
<style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600&display=swap');
*{font-family:'Inter',sans-serif;margin:0;padding:0}
.s{font-size:.75rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.08em}
</style><div class="s">📦 Active Shipments</div>""", height=24)

_raw = _load_shipments()

def _status_icon(status: str) -> str:
    s = status.lower()
    if "exception" in s or "fail" in s or "expired" in s: return "🔴 " + status
    if "attempt" in s or "pending" in s:                  return "🟡 " + status
    if "delivered" in s:                                   return "🟢 " + status
    return "🔵 " + status

if _raw:
    rows = []
    for t in _raw:
        risk_pct = int(t["risk"] * 100)
        rows.append({
            "Tracking #":   t["id"],
            "Carrier":      t["carrier"],
            "Status":       _status_icon(t["status"]),
            "Source":       t.get("source", "India"),
            "Destination":  t.get("destination", "India"),
            "Delay Risk":   f"{risk_pct}%",
            "ETA":          t.get("eta", "—")[:10] if t.get("eta") else "—",
            "Last Updated": t.get("last_updated", "—")[:16] if t.get("last_updated") else "—",
            "Data":         t.get("data_source", "AfterShip"),
        })

    df = pd.DataFrame(rows)

    def _style_status(col):
        return ["color:#fca5a5;font-weight:600" if "🔴" in v
                else "color:#fde68a;font-weight:600" if "🟡" in v
                else "color:#86efac;font-weight:600" if "🟢" in v
                else "color:#93c5fd;font-weight:600" for v in col]

    def _style_risk(col):
        out = []
        for v in col:
            p = float(v.strip("%")) / 100
            out.append("color:#fca5a5;font-weight:700" if p >= .70
                       else "color:#fde68a;font-weight:700" if p >= .40
                       else "color:#86efac")
        return out

    styled = df.style.apply(_style_status, subset=["Status"]).apply(_style_risk, subset=["Delay Risk"])
    st.dataframe(styled, use_container_width=True, hide_index=True, height=380)

    st.caption(f"Live data from AfterShip · {len(_raw)} shipment(s) · refreshes every 2 min")
else:
    st.info("No shipments tracked yet. Add real tracking numbers at admin.aftership.com → Tracking → Add shipment.")

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
