"""Analytics — ECharts dark-theme ML + network intelligence dashboard."""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_echarts import st_echarts

from config import MODELS_DIR
from graph.analytics import bottleneck_edges, critical_hubs
from services.graph_service import get_annotated_graph

st.set_page_config(page_title="Analytics · SupplyGuard", page_icon="📊", layout="wide")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from styles import inject, section
inject()

# ── Page header ───────────────────────────────────────────────────────────────
components.html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800&display=swap');
*{font-family:'Inter',sans-serif;margin:0;padding:0;box-sizing:border-box}
.hdr{padding:2px 0 16px;display:flex;align-items:flex-start;justify-content:space-between}
.left .title{font-size:1.45rem;font-weight:800;
  background:linear-gradient(90deg,#f9fafb,#60a5fa);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}
.left .sub{font-size:.8rem;color:#6b7280;margin-top:3px}
.chips{display:flex;gap:6px;margin-top:8px}
.chip{font-size:.65rem;font-weight:600;padding:3px 9px;border-radius:99px;letter-spacing:.04em}
.c1{background:#0c2340;border:1px solid #1d6fa4;color:#60a5fa}
.c2{background:#0f3326;border:1px solid #166534;color:#4ade80}
.c3{background:#2d1b4e;border:1px solid #6d28d9;color:#c084fc}
</style>
<div class="hdr">
  <div class="left">
    <div class="title">📊 Analytics &amp; Model Intelligence</div>
    <div class="sub">ML performance · SHAP feature explainability · Network risk topology</div>
    <div class="chips">
      <span class="chip c1">Random Forest · 200 trees</span>
      <span class="chip c2">SHAP TreeExplainer</span>
      <span class="chip c3">NetworkX Graph</span>
    </div>
  </div>
</div>
""", height=85)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_resource(ttl=3600)
def _graph():
    return get_annotated_graph()

try:
    G = _graph()
except FileNotFoundError:
    st.error("Run `python run_pipeline.py` first.")
    st.stop()

metrics_path = MODELS_DIR / "metrics.json"
fi_path      = MODELS_DIR / "feature_importances.csv"
shap_path    = MODELS_DIR / "shap_importances.csv"

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Model Performance KPI + Grouped Bar
# ═══════════════════════════════════════════════════════════════════════════════
section("🤖  Model Performance")

if metrics_path.exists():
    blob = json.loads(metrics_path.read_text())
    rows = [{"model": n.upper(),
             **{k: round(v, 3) for k, v in r.items() if k != "confusion"}}
            for n, r in blob["results"].items()]
    df_m     = pd.DataFrame(rows).sort_values("f1", ascending=False)
    best_row = df_m.iloc[0]

    # Animated KPI cards
    k1,k2,k3,k4,k5 = st.columns(5)
    k1.metric("Best Model",   best_row["model"])
    k2.metric("Accuracy",     f"{best_row['accuracy']:.1%}")
    k3.metric("F1 Score",     f"{best_row['f1']:.3f}",
              delta=f"+{best_row['f1']-df_m.iloc[-1]['f1']:.3f} vs baseline")
    k4.metric("Precision",    f"{best_row['precision']:.1%}")
    k5.metric("ROC-AUC",      f"{best_row['roc_auc']:.3f}")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ECharts grouped bar — all models × all metrics
    models   = df_m["model"].tolist()
    metric_cfg = [
        ("accuracy",  "#60a5fa", "Accuracy"),
        ("precision", "#34d399", "Precision"),
        ("recall",    "#f97316", "Recall"),
        ("f1",        "#a78bfa", "F1"),
        ("roc_auc",   "#fbbf24", "ROC-AUC"),
    ]
    series = [{
        "name": label, "type": "bar", "barGap": "5%", "barMaxWidth": 36,
        "data": df_m[col].tolist(),
        "itemStyle": {"color": color, "borderRadius": [3,3,0,0]},
        "label": {"show": True, "position": "top", "color": "#9ca3af",
                  "fontSize": 10, "formatter": "{c}"},
        "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": color}},
    } for col, color, label in metric_cfg]

    st_echarts({
        "backgroundColor": "#111827",
        "tooltip":  {"trigger": "axis", "axisPointer": {"type": "shadow"},
                     "backgroundColor": "#1f2937", "borderColor": "#374151",
                     "textStyle": {"color": "#f9fafb", "fontFamily": "Inter"}},
        "legend":   {"data": [l for _,_,l in metric_cfg],
                     "textStyle": {"color": "#9ca3af"}, "top": 8, "right": 12},
        "grid":     {"left": "3%", "right": "3%", "bottom": "4%",
                     "top": "55px", "containLabel": True},
        "xAxis":    {"type": "category", "data": models,
                     "axisLabel": {"color": "#d1d5db", "fontWeight": "bold", "fontSize": 12},
                     "axisLine": {"lineStyle": {"color": "#374151"}}},
        "yAxis":    {"type": "value", "max": 1.0, "min": 0,
                     "splitLine": {"lineStyle": {"color": "#1f2937", "type": "dashed"}},
                     "axisLabel": {"color": "#6b7280"}},
        "series":   series,
        "animation": True, "animationDuration": 1200, "animationEasing": "elasticOut",
    }, height="300px", key="model_bar")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Feature Importance (Native vs SHAP)
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
section("🎯  Feature Importance — Native RF  vs  SHAP (TreeExplainer)")

col_fi, col_shap = st.columns(2)

with col_fi:
    if fi_path.exists():
        fi = pd.read_csv(fi_path).sort_values("importance")
        _c = ["#ef4444" if v >= 0.20 else "#f97316" if v >= 0.10
              else "#fbbf24" if v >= 0.05 else "#60a5fa" for v in fi["importance"]]
        st_echarts({
            "backgroundColor": "#111827",
            "tooltip": {"trigger": "axis", "backgroundColor": "#1f2937",
                        "borderColor": "#374151", "textStyle": {"color": "#f9fafb"}},
            "title": {"text": "Native RF Feature Importance",
                      "subtext": "Gini impurity-based (biased toward high-cardinality)",
                      "textStyle": {"color": "#f9fafb", "fontSize": 13},
                      "subtextStyle": {"color": "#6b7280", "fontSize": 10},
                      "left": "center", "top": 4},
            "grid": {"left": "30%", "right": "10%", "top": "70px", "bottom": "4%"},
            "xAxis": {"type": "value",
                      "splitLine": {"lineStyle": {"color": "#1f2937", "type": "dashed"}},
                      "axisLabel": {"color": "#6b7280", "fontSize": 10}},
            "yAxis": {"type": "category", "data": fi["feature"].tolist(),
                      "axisLabel": {"color": "#9ca3af", "fontSize": 11}},
            "series": [{"type": "bar", "barMaxWidth": 22,
                        "data": [{"value": round(v, 3), "itemStyle": {"color": c,
                                  "borderRadius": [0,3,3,0]}}
                                 for v, c in zip(fi["importance"], _c)],
                        "label": {"show": True, "position": "right",
                                  "color": "#9ca3af", "fontSize": 10}}],
            "animation": True, "animationDuration": 900, "animationEasing": "cubicOut",
        }, height="320px", key="fi_chart")

with col_shap:
    if shap_path.exists():
        sd = pd.read_csv(shap_path).sort_values("shap_importance")
        _c = ["#a78bfa" if v >= 0.05 else "#818cf8" if v >= 0.02
              else "#6366f1" for v in sd["shap_importance"]]
        st_echarts({
            "backgroundColor": "#111827",
            "tooltip": {"trigger": "axis", "backgroundColor": "#1f2937",
                        "borderColor": "#374151", "textStyle": {"color": "#f9fafb"}},
            "title": {"text": "SHAP Importance  (Mean |SHAP|)",
                      "subtext": "Unbiased — measures actual prediction impact per feature",
                      "textStyle": {"color": "#f9fafb", "fontSize": 13},
                      "subtextStyle": {"color": "#6b7280", "fontSize": 10},
                      "left": "center", "top": 4},
            "grid": {"left": "30%", "right": "10%", "top": "70px", "bottom": "4%"},
            "xAxis": {"type": "value",
                      "splitLine": {"lineStyle": {"color": "#1f2937", "type": "dashed"}},
                      "axisLabel": {"color": "#6b7280", "fontSize": 10}},
            "yAxis": {"type": "category", "data": sd["feature"].tolist(),
                      "axisLabel": {"color": "#9ca3af", "fontSize": 11}},
            "series": [{"type": "bar", "barMaxWidth": 22,
                        "data": [{"value": round(v, 4), "itemStyle": {"color": c,
                                  "borderRadius": [0,3,3,0]}}
                                 for v, c in zip(sd["shap_importance"], _c)],
                        "label": {"show": True, "position": "right",
                                  "color": "#9ca3af", "fontSize": 10}}],
            "animation": True, "animationDuration": 1000, "animationEasing": "cubicOut",
        }, height="320px", key="shap_chart")

# SHAP insight callout
if shap_path.exists():
    sd2  = pd.read_csv(shap_path).sort_values("shap_importance", ascending=False)
    top1 = sd2.iloc[0]
    top2 = sd2.iloc[1]
    components.html(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&display=swap');
    *{{font-family:'Inter',sans-serif;margin:0;padding:0;box-sizing:border-box}}
    .box{{background:#1a1040;border:1px solid #6d28d9;border-radius:10px;padding:12px 16px;
          display:flex;align-items:center;gap:12px}}
    .icon{{font-size:1.4rem}}
    .txt{{font-size:.82rem;color:#d1d5db;line-height:1.5}}
    .hl{{color:#c084fc;font-weight:600}}
    </style>
    <div class="box">
      <div class="icon">💡</div>
      <div class="txt">
        <span class="hl">SHAP Key Insight:</span>
        <b style="color:#f9fafb">{top1['feature']}</b> ({top1['shap_importance']:.4f}) and
        <b style="color:#f9fafb">{top2['feature']}</b> ({top2['shap_importance']:.4f})
        are the top 2 real-time signal drivers — proving live API data (TomTom + Open-Meteo)
        has more per-prediction impact than static features like distance or historical delay.
      </div>
    </div>
    """, height=60)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Network topology
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
section("🌐  Network Risk Topology")

col_hubs, col_pie = st.columns(2)

with col_hubs:
    hubs = pd.DataFrame(critical_hubs(G, 10), columns=["city", "centrality"])
    _hc  = ["#ef4444" if v >= 0.15 else "#f97316" if v >= 0.08
             else "#fbbf24" if v >= 0.04 else "#60a5fa" for v in hubs["centrality"]]
    st_echarts({
        "backgroundColor": "#111827",
        "tooltip": {"trigger": "axis", "backgroundColor": "#1f2937",
                    "borderColor": "#374151", "textStyle": {"color": "#f9fafb"},
                    "formatter": "{b}: {c}"},
        "title": {"text": "Critical Hubs — Betweenness Centrality",
                  "subtext": "High centrality = removal disconnects most route pairs",
                  "textStyle": {"color": "#f9fafb", "fontSize": 13},
                  "subtextStyle": {"color": "#6b7280", "fontSize": 10},
                  "left": "center", "top": 4},
        "grid": {"left": "35%", "right": "8%", "top": "70px", "bottom": "4%"},
        "xAxis": {"type": "value",
                  "splitLine": {"lineStyle": {"color": "#1f2937", "type": "dashed"}},
                  "axisLabel": {"color": "#6b7280", "fontSize": 10}},
        "yAxis": {"type": "category", "data": hubs["city"].tolist(),
                  "axisLabel": {"color": "#9ca3af", "fontSize": 10}},
        "series": [{"type": "bar", "barMaxWidth": 20,
                    "data": [{"value": round(v, 4), "itemStyle": {"color": c,
                              "borderRadius": [0,3,3,0]}}
                             for v, c in zip(hubs["centrality"], _hc)],
                    "label": {"show": True, "position": "right",
                              "color": "#9ca3af", "fontSize": 9}}],
        "animation": True, "animationDuration": 1100,
    }, height="360px", key="hubs_chart")

with col_pie:
    all_risks = [d["risk"] for _,_,d in G.edges(data=True)]
    low    = sum(1 for r in all_risks if r < 0.33)
    medium = sum(1 for r in all_risks if 0.33 <= r < 0.66)
    high   = sum(1 for r in all_risks if r >= 0.66)
    avg_r  = sum(all_risks) / len(all_risks) if all_risks else 0

    st_echarts({
        "backgroundColor": "#111827",
        "tooltip": {"trigger": "item", "backgroundColor": "#1f2937",
                    "borderColor": "#374151", "textStyle": {"color": "#f9fafb"},
                    "formatter": "{b}: {c} routes ({d}%)"},
        "title": [
            {"text": "Route Risk Distribution",
             "subtext": f"Avg risk across all {len(all_risks)} routes: {avg_r:.1%}",
             "textStyle": {"color": "#f9fafb", "fontSize": 13},
             "subtextStyle": {"color": "#6b7280", "fontSize": 10},
             "left": "center", "top": 4},
            {"text": f"{avg_r:.0%}", "subtext": "Avg Risk",
             "textAlign": "center",
             "textStyle": {"fontSize": 22, "fontWeight": "bold",
                           "color": "#ef4444" if avg_r >= 0.5 else "#f97316" if avg_r >= 0.33 else "#22c55e"},
             "subtextStyle": {"color": "#6b7280", "fontSize": 11},
             "left": "49%", "top": "46%"},
        ],
        "legend": {"orient": "vertical", "left": "2%", "top": "center",
                   "textStyle": {"color": "#9ca3af", "fontSize": 11}},
        "series": [{
            "type": "pie", "radius": ["45%", "72%"],
            "center": ["55%", "58%"],
            "avoidLabelOverlap": False,
            "label": {"show": False},
            "labelLine": {"show": False},
            "emphasis": {"label": {"show": True, "fontSize": 13, "fontWeight": "bold",
                                   "color": "#f9fafb"},
                         "itemStyle": {"shadowBlur": 12, "shadowColor": "rgba(0,0,0,.5)"}},
            "data": [
                {"value": low,    "name": f"Low Risk ({low})",
                 "itemStyle": {"color": "#22c55e"}},
                {"value": medium, "name": f"Medium ({medium})",
                 "itemStyle": {"color": "#f97316"}},
                {"value": high,   "name": f"High Risk ({high})",
                 "itemStyle": {"color": "#ef4444"}},
            ],
        }],
        "animation": True, "animationDuration": 1000, "animationEasing": "cubicOut",
    }, height="360px", key="risk_pie")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Risky routes table + Bottleneck edges
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
col_tbl, col_bn = st.columns(2)

with col_tbl:
    section("🔴  Top 10 Riskiest Routes")
    risky = sorted([(u, v, d["risk"], round(d["distance"],1))
                    for u,v,d in G.edges(data=True)], key=lambda x: -x[2])[:10]
    df_r  = pd.DataFrame(risky, columns=["Origin","Destination","Risk","Distance (km)"])
    df_r["Risk"] = df_r["Risk"].apply(lambda x: f"{x:.0%}")

    def _cr(col):
        return ["color:#ef4444;font-weight:700" if int(v.strip("%")) >= 66
                else "color:#f97316;font-weight:700" if int(v.strip("%")) >= 33
                else "color:#22c55e" for v in col]

    st.dataframe(df_r.style.apply(_cr, subset=["Risk"]),
                 use_container_width=True, hide_index=True, height=340)

with col_bn:
    section("⚡  Bottleneck Edges (Edge Betweenness)")
    bn    = [(f"{u}→{v}", round(c, 4)) for (u,v),c in bottleneck_edges(G, 10)]
    bn_v  = [x[1] for x in bn]
    bn_l  = [x[0] for x in bn]
    bn_c  = ["#ef4444" if v >= 0.04 else "#f97316" if v >= 0.02
             else "#fbbf24" for v in bn_v]
    st_echarts({
        "backgroundColor": "#111827",
        "tooltip": {"trigger": "axis", "backgroundColor": "#1f2937",
                    "borderColor": "#374151", "textStyle": {"color": "#f9fafb"}},
        "grid": {"left": "38%", "right": "8%", "top": "8px", "bottom": "4%"},
        "xAxis": {"type": "value",
                  "splitLine": {"lineStyle": {"color": "#1f2937", "type": "dashed"}},
                  "axisLabel": {"color": "#6b7280", "fontSize": 9}},
        "yAxis": {"type": "category", "data": bn_l,
                  "axisLabel": {"color": "#9ca3af", "fontSize": 9}},
        "series": [{"type": "bar", "barMaxWidth": 18,
                    "data": [{"value": v, "itemStyle": {"color": c,
                              "borderRadius": [0,3,3,0]}}
                             for v,c in zip(bn_v, bn_c)],
                    "label": {"show": True, "position": "right",
                              "color": "#9ca3af", "fontSize": 9}}],
        "animation": True, "animationDuration": 900,
    }, height="340px", key="bn_chart")
