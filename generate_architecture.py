"""Generate a professional system architecture diagram for SupplyGuard."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(20, 14))
ax.set_xlim(0, 20)
ax.set_ylim(0, 14)
ax.axis('off')
fig.patch.set_facecolor('#0d1117')

# ── Colour palette ────────────────────────────────────────────────────────────
C = {
    'bg':       '#0d1117',
    'l1_bg':    '#0f2942',   # Data  – deep blue
    'l1_bdr':   '#1d6fa4',
    'l2_bg':    '#1a1a2e',   # Graph – dark purple
    'l2_bdr':   '#6c3fc5',
    'l3_bg':    '#0f3326',   # ML    – deep green
    'l3_bdr':   '#22c55e',
    'l4_bg':    '#2a1a0f',   # Svc   – dark amber
    'l4_bdr':   '#f97316',
    'l5_bg':    '#1a0a2e',   # UI    – dark violet
    'l5_bdr':   '#a855f7',
    'api_bg':   '#0c2340',
    'api_bdr':  '#38bdf8',
    'arrow':    '#475569',
    'white':    '#f1f5f9',
    'muted':    '#94a3b8',
    'highlight':'#fbbf24',
}

def box(ax, x, y, w, h, bg, bdr, radius=0.25, lw=2, alpha=1.0):
    rect = FancyBboxPatch((x, y), w, h,
                          boxstyle=f"round,pad=0,rounding_size={radius}",
                          linewidth=lw, edgecolor=bdr,
                          facecolor=bg, alpha=alpha, zorder=3)
    ax.add_patch(rect)

def label(ax, x, y, text, size=9, color='#f1f5f9', weight='normal',
          ha='center', va='center', zorder=5):
    ax.text(x, y, text, fontsize=size, color=color,
            fontweight=weight, ha=ha, va=va, zorder=zorder,
            fontfamily='monospace')

def arrow(ax, x1, y1, x2, y2, color='#475569', lw=1.8, style='->', bidirectional=False):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color,
                                lw=lw, connectionstyle='arc3,rad=0.0'),
                zorder=2)
    if bidirectional:
        ax.annotate('', xy=(x1, y1), xytext=(x2, y2),
                    arrowprops=dict(arrowstyle=style, color=color,
                                    lw=lw, connectionstyle='arc3,rad=0.0'),
                    zorder=2)

# ═══════════════════════════════════════════════════════════════════════════════
# TITLE
# ═══════════════════════════════════════════════════════════════════════════════
ax.text(10, 13.5, 'SupplyGuard — System Architecture',
        fontsize=18, color=C['white'], fontweight='bold',
        ha='center', va='center', fontfamily='sans-serif')
ax.text(10, 13.1, 'Real-Time Supply Chain Risk Intelligence Platform',
        fontsize=11, color=C['muted'], ha='center', va='center')

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — DATA (bottom)  y = 0.3 → 2.4
# ═══════════════════════════════════════════════════════════════════════════════
box(ax, 0.3, 0.3, 19.4, 2.2, C['l1_bg'], C['l1_bdr'], lw=2)
label(ax, 1.95, 2.25, 'LAYER 1', 8, C['l1_bdr'], 'bold', ha='center')
label(ax, 1.95, 2.0,  'DATA INGESTION', 7, C['muted'], ha='center')

# API boxes
apis = [
    ('Open-Meteo API',    'Weather · WMO code\nPrecip · Windspeed\n5 hub cities\nFree · No key',       '#0369a1', '#7dd3fc'),
    ('OpenSky Network',   'ADS-B Transponder\nIndia bbox query\n27 cargo prefixes\nFree · No key',     '#065f46', '#6ee7b7'),
    ('aisstream.io AIS',  'WebSocket stream\nAIS Type 1/2/3/5\n300 vessels · 7s\nFree · API key',      '#581c87', '#d8b4fe'),
    ('TomTom Flow API',   'Road segments\ncurrentSpeed\nfreeFlowSpeed\nFree tier · 2500/day','#7c2d12', '#fdba74'),
    ('E-Commerce CSV',    'Train.csv · 10,999\nshipment records\nBinary delay label\nStatic dataset',  '#1e3a5f', '#93c5fd'),
]

api_xs = [0.55, 4.35, 8.15, 11.95, 15.75]
for i, (title, desc, abg, abdr) in enumerate(apis):
    x = api_xs[i]
    box(ax, x, 0.45, 3.5, 1.8, abg, abdr, radius=0.18, lw=1.5)
    label(ax, x+1.75, 2.05, title, 8.5, abdr, 'bold')
    for j, line in enumerate(desc.split('\n')):
        label(ax, x+1.75, 1.72 - j*0.28, line, 7.5, C['white'])

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — GRAPH  (left-bottom mid)  x=0.3..6.5  y=2.9..5.8
# ═══════════════════════════════════════════════════════════════════════════════
box(ax, 0.3, 2.9, 5.9, 3.0, C['l2_bg'], C['l2_bdr'], lw=2)
label(ax, 3.25, 5.65, 'LAYER 2 — GRAPH ENGINE', 9, C['l2_bdr'], 'bold')

graph_items = [
    ('graph_builder.py',  'DiGraph  15 nodes · 36 edges'),
    ('analytics.py',      'Betweenness · Closeness · Degree'),
    ('simulation.py',     'WCC cascade failure iteration'),
    ('routing.py',        'Dijkstra  (weight = risk score)'),
    ('NetworkX 3.2',      'In-memory graph  sub-100 ms ops'),
]
for i, (fn, desc) in enumerate(graph_items):
    y = 5.15 - i * 0.44
    label(ax, 1.35, y, fn,   8, C['l2_bdr'], 'bold',   ha='left')
    label(ax, 1.35, y-0.18, desc, 7.5, C['muted'], ha='left')

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — ML  (right-bottom mid)  x=7.0..13.2  y=2.9..5.8
# ═══════════════════════════════════════════════════════════════════════════════
box(ax, 6.5, 2.9, 6.5, 3.0, C['l3_bg'], C['l3_bdr'], lw=2)
label(ax, 9.75, 5.65, 'LAYER 3 — ML ENGINE', 9, C['l3_bdr'], 'bold')

ml_items = [
    ('preprocess.py',     'Feature engineer  9-column vector'),
    ('train_model.py',    'LogReg baseline  +  RF 200 trees'),
    ('SHAP explainer',    'TreeExplainer  mean |SHAP| ranking'),
    ('delay_rf.joblib',   'Persisted model  <5 ms inference'),
    ('metrics.json',      'F1=0.333  AUC=0.614  (RF winner)'),
]
for i, (fn, desc) in enumerate(ml_items):
    y = 5.15 - i * 0.44
    label(ax, 6.75, y, fn,   8, C['l3_bdr'], 'bold',   ha='left')
    label(ax, 6.75, y-0.18, desc, 7.5, C['muted'], ha='left')

# ═══════════════════════════════════════════════════════════════════════════════
# 9 FEATURES BOX  (right side)  x=13.4..19.7  y=2.9..5.8
# ═══════════════════════════════════════════════════════════════════════════════
box(ax, 13.3, 2.9, 6.4, 3.0, '#0f1a2e', '#334155', lw=1.5)
label(ax, 16.5, 5.65, '9 FEATURE VECTOR', 9, C['highlight'], 'bold')

features = [
    ('weather_score',       '← Open-Meteo',    C['api_bdr']),
    ('traffic_score',       '← TomTom Flow',   '#fb923c'),
    ('port_congestion',     '← aisstream.io',  '#c084fc'),
    ('flight_delay_min',    '← OpenSky Net.',  '#4ade80'),
    ('vessel_delay_hrs',    '← aisstream.io',  '#c084fc'),
    ('distance_km',         '← Static CSV',    C['muted']),
    ('warehouse_load',      '← Graph model',   C['muted']),
    ('hist_avg_delay_hrs',  '← Corpus stats',  C['muted']),
    ('transport_mode',      '← Static CSV',    C['muted']),
]
for i, (feat, src, col) in enumerate(features):
    y = 5.18 - i * 0.30
    label(ax, 13.55, y, f'• {feat}', 7.5, col, ha='left')
    label(ax, 18.85, y, src, 7, C['muted'], ha='right')

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 4 — SERVICES  y=6.3..8.5
# ═══════════════════════════════════════════════════════════════════════════════
box(ax, 0.3, 6.3, 19.4, 2.3, C['l4_bg'], C['l4_bdr'], lw=2)
label(ax, 3.0, 8.38, 'LAYER 4 — SERVICES  (Pure Python · No UI imports)', 9, C['l4_bdr'], 'bold')

services = [
    ('prediction_service', 'predict_delay(9 feats)\n→ probability · score · level'),
    ('graph_service',      'get_annotated_graph()\noverview_metrics()'),
    ('routing_service',    'find_alternate_route()\n(src, dst, graph)'),
    ('weather_service',    'get_weather(city)\n→ score · label · mm · kmh'),
    ('vessel_service',     'get_vessels_near_india()\nget_port_congestion(port)'),
    ('flight_service',     'get_cargo_flights()\nget_flight_delay_risk()'),
    ('traffic_service',    'get_traffic(origin, dest)\n→ score · ratio · speed'),
]
svc_xs = [0.5, 3.3, 6.1, 8.9, 11.7, 14.5, 17.3]
for i, (name, desc) in enumerate(services):
    x = svc_xs[i]
    box(ax, x, 6.48, 2.6, 1.65, '#1c0f00', C['l4_bdr'], radius=0.15, lw=1.5)
    label(ax, x+1.3, 7.95, name, 7.5, C['l4_bdr'], 'bold')
    for j, line in enumerate(desc.split('\n')):
        label(ax, x+1.3, 7.63 - j*0.3, line, 7, C['muted'])

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 5 — PRESENTATION  y=9.0..11.5
# ═══════════════════════════════════════════════════════════════════════════════
box(ax, 0.3, 9.0, 19.4, 2.6, C['l5_bg'], C['l5_bdr'], lw=2)
label(ax, 3.2, 11.35, 'LAYER 5 — PRESENTATION  (Streamlit Multi-Page Dashboard)', 9, C['l5_bdr'], 'bold')

pages = [
    ('[Home]',
     'KPI cards · Threat feed\nIndia risk map · Vessel\nfeed · Flight count',
     '#6d28d9'),
    ('[Predict]',
     'Delay predictor form\nRF inference · Risk level\nAlternate route output',
     '#0891b2'),
    ('[Map]',
     'Folium choropleth\nGreen/Orange/Red edges\nNode hover tooltips',
     '#059669'),
    ('[Simulate]',
     'Hub failure selector\nCascade WCC analysis\nRisk delta table',
     '#dc2626'),
    ('[Analytics]',
     'SHAP bar chart\nCentrality rankings\nTop-10 risky routes',
     '#d97706'),
]
pg_xs = [0.55, 4.35, 8.15, 11.95, 15.75]
for i, (title, desc, col) in enumerate(pages):
    x = pg_xs[i]
    box(ax, x, 9.18, 3.5, 1.98, '#12082a', col, radius=0.18, lw=1.8)
    label(ax, x+1.75, 10.97, title, 9, col, 'bold')
    for j, line in enumerate(desc.split('\n')):
        label(ax, x+1.75, 10.62 - j*0.28, line, 7.5, C['white'])

# ═══════════════════════════════════════════════════════════════════════════════
# ARROWS
# ═══════════════════════════════════════════════════════════════════════════════
# Data → Graph, ML, Features
arrow(ax, 10.0, 2.55, 3.25, 2.9,  C['l1_bdr'], 1.8)
arrow(ax, 10.0, 2.55, 9.75, 2.9,  C['l1_bdr'], 1.8)
arrow(ax, 10.0, 2.55, 16.5, 2.9,  C['l1_bdr'], 1.8)

# Graph + ML + Features → Services
arrow(ax, 3.25, 5.9,  5.0,  6.3,  C['l2_bdr'], 1.8)
arrow(ax, 9.75, 5.9,  10.0, 6.3,  C['l3_bdr'], 1.8)
arrow(ax, 16.5, 5.9,  15.0, 6.3,  C['highlight'], 1.8)

# Services → Dashboard
arrow(ax, 10.0, 8.6,  10.0, 9.0,  C['l4_bdr'], 2.0)


# ── Layer labels on left margin ───────────────────────────────────────────────
for y_mid, tag, col in [
    (1.4,  'L1\nDATA',  C['l1_bdr']),
    (4.35, 'L2\nGRAPH', C['l2_bdr']),
    (4.35, '',          ''),   # ML shares same row — skip
    (7.45, 'L4\nSVC',   C['l4_bdr']),
    (10.3, 'L5\nUI',    C['l5_bdr']),
]:
    if tag:
        ax.text(0.08, y_mid, tag, fontsize=7, color=col,
                fontweight='bold', ha='center', va='center',
                rotation=90, fontfamily='monospace')

ax.text(0.08, 4.35, 'L3\nML', fontsize=7, color=C['l3_bdr'],
        fontweight='bold', ha='center', va='center',
        rotation=90, fontfamily='monospace')

plt.tight_layout(pad=0)
out = 'supply-chain-risk/SupplyGuard_Architecture.png'
plt.savefig(out, dpi=180, bbox_inches='tight',
            facecolor=C['bg'], edgecolor='none')
print(f"Saved: {out}")
plt.close()
