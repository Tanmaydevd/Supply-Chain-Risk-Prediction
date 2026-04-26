"""Analytics page — model performance, feature importance, network insights."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from config import MODELS_DIR
from graph.analytics import bottleneck_edges, critical_hubs
from services.graph_service import get_annotated_graph

st.set_page_config(page_title="Analytics", page_icon="📊", layout="wide")
st.title("📊 Network & Model Analytics")

try:
    G = get_annotated_graph()
except FileNotFoundError:
    st.error("Model not trained. Run `python -m ml.train_model` first.")
    st.stop()


# ---------- Model performance ----------
st.header("🤖 Model performance")
metrics_path = MODELS_DIR / "metrics.json"
if metrics_path.exists():
    blob = json.loads(metrics_path.read_text())
    rows = []
    for name, r in blob["results"].items():
        rows.append(
            {
                "model": name,
                "accuracy": round(r["accuracy"], 3),
                "precision": round(r["precision"], 3),
                "recall": round(r["recall"], 3),
                "f1": round(r["f1"], 3),
                "roc_auc": round(r["roc_auc"], 3),
            }
        )
    df_m = pd.DataFrame(rows).sort_values("f1", ascending=False)
    st.caption(f"Best model: **{blob['best']}** (highest F1)")
    st.dataframe(df_m, use_container_width=True, hide_index=True)
    st.plotly_chart(
        px.bar(df_m, x="model", y="f1", color="model", title="F1 by model"),
        use_container_width=True,
    )
else:
    st.info("Train models first to see comparison: `python -m ml.train_model`.")


# ---------- Feature importance ----------
st.header("🎯 Feature importance (winning model)")
fi_path = MODELS_DIR / "feature_importances.csv"
shap_path = MODELS_DIR / "shap_importances.csv"

col_fi, col_shap = st.columns(2)

with col_fi:
    st.subheader("Native importance")
    if fi_path.exists():
        fi = pd.read_csv(fi_path)
        st.plotly_chart(
            px.bar(fi, x="feature", y="importance", color="importance",
                   color_continuous_scale="Blues",
                   title="Native feature importance"),
            use_container_width=True,
        )
        top = fi.iloc[0]
        st.caption(f"Top: **{top['feature']}** ({top['importance']:.2f})")
    else:
        st.info("Run `python -m ml.train_model` first.")

with col_shap:
    st.subheader("SHAP importance (paper §3.5)")
    if shap_path.exists():
        shap_df = pd.read_csv(shap_path)
        st.plotly_chart(
            px.bar(shap_df, x="feature", y="shap_importance",
                   color="shap_importance",
                   color_continuous_scale="Oranges",
                   title="Mean |SHAP| — model-agnostic explainability"),
            use_container_width=True,
        )
        selected = shap_df[shap_df.shap_importance >= 0.01]["feature"].tolist()
        st.caption(
            f"Paper threshold ≥0.01 selects: **{', '.join(selected)}**"
        )
    else:
        st.info("SHAP values not computed yet — retrain to generate.")


# ---------- Network analytics ----------
st.header("🌐 Network analytics")

st.subheader("Top critical hubs (betweenness centrality)")
hubs = pd.DataFrame(critical_hubs(G, 5), columns=["city", "centrality"])
st.plotly_chart(
    px.bar(hubs, x="city", y="centrality", color="centrality",
           color_continuous_scale="Reds",
           title="Hubs whose removal disconnects the most pairs"),
    use_container_width=True,
)

st.subheader("Top 10 risky routes")
risky = sorted(
    [(u, v, d["risk"], d["distance"]) for u, v, d in G.edges(data=True)],
    key=lambda x: -x[2],
)[:10]
df = pd.DataFrame(risky, columns=["origin", "destination", "risk", "distance_km"])
df["risk"] = df["risk"].round(3)
st.dataframe(df, use_container_width=True, hide_index=True)

st.subheader("Risk distribution across all routes")
all_risks = pd.DataFrame(
    [{"risk": d["risk"], "level": d["risk_level"]} for _, _, d in G.edges(data=True)]
)
st.plotly_chart(
    px.histogram(all_risks, x="risk", color="level", nbins=20,
                 title="Risk distribution"),
    use_container_width=True,
)

st.subheader("Top bottleneck edges (edge betweenness)")
bn = pd.DataFrame(
    [(f"{u}→{v}", c) for (u, v), c in bottleneck_edges(G, 5)],
    columns=["edge", "edge_betweenness"],
)
st.plotly_chart(
    px.bar(bn, x="edge", y="edge_betweenness",
           title="Edges most often on shortest paths"),
    use_container_width=True,
)
