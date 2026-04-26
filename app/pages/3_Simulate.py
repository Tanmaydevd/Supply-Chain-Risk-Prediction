"""Simulate page — cascading failure + risk-impact quantification.

Results are stored in st.session_state so they persist across reruns
(Streamlit reruns on every widget interaction, which was causing results
to disappear immediately after rendering).
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from graph.graph_builder import annotate_with_risk, build_graph
from graph.simulation import cascade_failure, risk_impact
from services.graph_service import all_nodes

st.set_page_config(page_title="Simulate", page_icon="💥", layout="wide")
st.title("💥 Cascading Failure Simulation")
st.markdown(
    "Simulate a **warehouse outage, port strike, or hub closure**. "
    "The engine cascades the failure through the network (WCC-based), "
    "re-predicts delay on surviving routes under rerouted load, "
    "and maps the post-failure risk landscape."
)

# ── load graph + model guard ──────────────────────────────────────────────────
try:
    nodes = all_nodes()
    G_full = build_graph()
    G_annotated = annotate_with_risk(G_full)
except FileNotFoundError:
    st.error("Model not trained yet. Run `python run_pipeline.py` first.")
    st.stop()

# ── session state init ────────────────────────────────────────────────────────
if "sim_result" not in st.session_state:
    st.session_state.sim_result = None      # dict from cascade_failure
if "sim_impact" not in st.session_state:
    st.session_state.sim_impact = None      # list from risk_impact
if "sim_G_post" not in st.session_state:
    st.session_state.sim_G_post = None      # annotated surviving graph
if "sim_failed" not in st.session_state:
    st.session_state.sim_failed = None
if "sim_extra_load" not in st.session_state:
    st.session_state.sim_extra_load = None

# ── controls ──────────────────────────────────────────────────────────────────
col_sel, col_load = st.columns([2, 1])
failed = col_sel.selectbox(
    "Select node to fail (hub, warehouse, or port)",
    nodes,
    help="Removing a high-betweenness node causes the most cascading damage.",
)
extra_load = col_load.slider(
    "Extra load on surviving routes (%)",
    5, 40, 15,
    help="Rerouted traffic raises warehouse load on surviving edges.",
) / 100.0

col_run, col_clear = st.columns([3, 1])
run = col_run.button("Run Simulation", type="primary", use_container_width=True)
clear = col_clear.button("Clear", use_container_width=True)

if clear:
    st.session_state.sim_result = None
    st.session_state.sim_impact = None
    st.session_state.sim_G_post = None
    st.session_state.sim_failed = None
    st.session_state.sim_extra_load = None
    st.rerun()

# ── run simulation (only when button clicked) ─────────────────────────────────
if run:
    with st.spinner(f"Simulating failure of {failed}..."):
        res = cascade_failure(G_annotated, failed)
        G_post = res["surviving_graph"]

        for u, v, d in G_annotated.edges(data=True):
            if G_post.has_edge(u, v):
                G_post[u][v]["risk"] = d.get("risk", 0.5)
                G_post[u][v]["risk_level"] = d.get("risk_level", "Medium")
                G_post[u][v]["load"] = 0.7

        impact_rows = risk_impact(G_annotated, G_post, load_increase=extra_load)
        G_post = annotate_with_risk(
            G_post,
            default_weather=1,
            default_traffic=1,
            default_load=min(0.7 + extra_load, 1.0),
        )

        # persist to session state
        st.session_state.sim_result = res
        st.session_state.sim_impact = impact_rows
        st.session_state.sim_G_post = G_post
        st.session_state.sim_failed = failed
        st.session_state.sim_extra_load = extra_load

# ── display results (from session state) ──────────────────────────────────────
if st.session_state.sim_result is None:
    st.info("Pick a node above and click **Run Simulation**.")
    st.stop()

# pull from session state (survive any subsequent widget interaction)
res = st.session_state.sim_result
impact_rows = st.session_state.sim_impact
G_post = st.session_state.sim_G_post
sim_failed = st.session_state.sim_failed
sim_extra_load = st.session_state.sim_extra_load

st.divider()
st.caption(f"Showing results for: **{sim_failed}** failure  |  extra load: **{sim_extra_load:.0%}**")

# ── KPI metrics ───────────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Lost edges", res["lost_edges"],
          delta=f"-{res['lost_edges']}", delta_color="inverse")
m2.metric("Secondary failures", len(res["secondary_failures"]),
          help="Nodes cascaded out after primary removal")
m3.metric("Remaining nodes", res["remaining_nodes"])
m4.metric("Remaining edges", res["remaining_edges"])
avg_delta = (
    sum(r["delta"] for r in impact_rows if r["delta"] is not None) / len(impact_rows)
    if impact_rows else 0
)
m5.metric("Avg delay risk increase", f"+{avg_delta:.1%}",
          delta=f"+{avg_delta:.1%}", delta_color="inverse")

# ── cascade status ────────────────────────────────────────────────────────────
if res["secondary_failures"]:
    st.error(
        f"**Cascade order:** {' -> '.join(res['cascade_order'])}  \n"
        f"Secondary failures (cut off from network): {', '.join(res['secondary_failures'])}"
    )
else:
    st.success(
        f"**{sim_failed}** removed. Network remains fully connected — "
        "no secondary cascading failures."
    )

# ── affected routes ───────────────────────────────────────────────────────────
with st.expander(f"Affected routes ({len(res['affected_routes'])})", expanded=False):
    if res["affected_routes"]:
        for u, v in sorted(res["affected_routes"]):
            st.write(f"  {u} -> {v}")
    else:
        st.write("None.")

# ── risk-impact table ─────────────────────────────────────────────────────────
st.divider()
st.subheader("Risk impact on surviving routes (after rerouting)")
st.caption(
    f"Surviving routes carry +{sim_extra_load:.0%} extra warehouse load from rerouted shipments. "
    "Delta = post-failure delay probability minus pre-failure."
)

if impact_rows:
    df_impact = pd.DataFrame(impact_rows)
    df_impact = df_impact[["route", "risk_before", "risk_after", "delta", "risk_level_after"]]
    df_impact.columns = ["Route", "Risk before", "Risk after", "Delta", "Level (after)"]

    def _color_delta(val):
        if val > 0.05:
            return "color: #c62828"
        if val > 0:
            return "color: #e65100"
        return "color: #2e7d32"

    styled = (
        df_impact.style
        .map(_color_delta, subset=["Delta"])
        .format({"Risk before": "{:.1%}", "Risk after": "{:.1%}", "Delta": "{:+.1%}"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    fig = px.bar(
        df_impact.head(15), x="Route", y="Delta",
        color="Delta",
        color_continuous_scale=["green", "orange", "red"],
        title="Delay risk increase per surviving route (top 15)",
        labels={"Delta": "Risk increase"},
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

# ── post-failure map ──────────────────────────────────────────────────────────
st.divider()
st.subheader("Network after failure")
st.caption(
    "Red marker = failed node  ·  Orange marker = cascaded secondary failure  ·  "
    "Edge colour = ML-predicted delay risk on surviving network"
)


def _edge_color(r: float) -> str:
    return "#43a047" if r < 0.33 else "#fb8c00" if r < 0.66 else "#e53935"


m_map = folium.Map(location=[22.0, 79.0], zoom_start=5, tiles="cartodbpositron")

fd = G_full.nodes[sim_failed]
folium.Marker(
    [fd["lat"], fd["lon"]],
    popup=f"FAILED: {sim_failed}",
    icon=folium.Icon(color="red", icon="remove"),
).add_to(m_map)

for sf in res["secondary_failures"]:
    if sf in G_full.nodes:
        sfd = G_full.nodes[sf]
        folium.Marker(
            [sfd["lat"], sfd["lon"]],
            popup=f"Cascaded failure: {sf}",
            icon=folium.Icon(color="orange", icon="warning-sign"),
        ).add_to(m_map)

for n, d in G_post.nodes(data=True):
    folium.CircleMarker(
        [d["lat"], d["lon"]],
        radius=7,
        popup=f"{n} ({d.get('type', '')})",
        color="#1565c0",
        fill=True, fill_opacity=0.85,
    ).add_to(m_map)

for u, v, d in G_post.edges(data=True):
    a, b = G_post.nodes[u], G_post.nodes[v]
    risk_val = d.get("risk", 0.5)
    folium.PolyLine(
        [(a["lat"], a["lon"]), (b["lat"], b["lon"])],
        color=_edge_color(risk_val),
        weight=3, opacity=0.75,
        tooltip=f"{u} -> {v}  risk={risk_val:.0%}  ({d.get('risk_level', '')})",
    ).add_to(m_map)

st_folium(m_map, width=None, height=560, key=f"sim-map-{sim_failed}")

st.caption("🟢 Low risk (<33%)  ·  🟠 Medium (33–66%)  ·  🔴 High (>66%)")

# ── delivery-step impact (paper §3.3) ─────────────────────────────────────────
st.divider()
st.subheader("Delivery-step impact (paper §3.3 — 11-step flow)")
st.caption(
    "Steps that route THROUGH the failed node are marked as impacted "
    "and gain extra delay risk proportional to the extra load slider."
)

DELIVERY_STEPS = [
    "delivery_collection", "loading_initial_unit",
    "transferring_to_first_transfer", "unloading_first_transfer",
    "handling_first_transfer", "loading_first_transfer",
    "transferring_to_terminal_unit", "unloading_terminal_unit",
    "handling_terminal_unit", "handling_courier", "delivery",
]

hub_importance = {
    "hub":       ["unloading_first_transfer", "handling_first_transfer",
                  "loading_first_transfer", "transferring_to_terminal_unit"],
    "port":      ["delivery_collection", "loading_initial_unit",
                  "transferring_to_first_transfer"],
    "warehouse": ["unloading_terminal_unit", "handling_terminal_unit",
                  "handling_courier", "delivery"],
}

node_type = G_full.nodes[sim_failed].get("type", "hub")
impacted_steps = set(hub_importance.get(node_type, []))

step_rows = []
for step in DELIVERY_STEPS:
    impacted = step in impacted_steps
    step_risk = min(0.32 + sim_extra_load if impacted else 0.32, 0.99)
    step_rows.append({
        "Step": step.replace("_", " ").title(),
        "Impacted": "Yes" if impacted else "—",
        "Delay risk (post-failure)": step_risk,
    })

df_steps = pd.DataFrame(step_rows)
fig2 = px.bar(
    df_steps, x="Step", y="Delay risk (post-failure)",
    color="Impacted",
    color_discrete_map={"Yes": "#e53935", "—": "#43a047"},
    title=f"11-step delivery risk after {sim_failed} failure",
)
fig2.add_hline(y=0.32, line_dash="dot", line_color="grey",
               annotation_text="Baseline 32%")
fig2.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig2, use_container_width=True)
