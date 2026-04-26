"""Build a NetworkX directed graph from data/processed/{nodes,edges}.csv."""
from __future__ import annotations
import networkx as nx
import pandas as pd

from config import DATA_PROCESSED


def build_graph() -> nx.DiGraph:
    nodes = pd.read_csv(DATA_PROCESSED / "nodes.csv")
    edges = pd.read_csv(DATA_PROCESSED / "edges.csv")
    G = nx.DiGraph()
    # nodes.csv now has: name, lat, lon, type, subtype  (new schema)
    #                 or city, lat, lon, type            (old schema)
    name_col = "name" if "name" in nodes.columns else "city"
    for _, n in nodes.iterrows():
        G.add_node(
            n[name_col],
            lat=float(n.lat), lon=float(n.lon),
            type=n.get("type", "warehouse"),
            subtype=n.get("subtype", ""),
        )
    for _, e in edges.iterrows():
        G.add_edge(
            e.origin, e.destination,
            distance=float(e.distance_km),
            hist_delay=float(e.hist_avg_delay_hrs),
            transport_mode=int(e.get("transport_mode", 0)),
        )
    return G


def annotate_with_risk(
    G: nx.DiGraph,
    default_weather: int = 1,
    default_traffic: int = 1,
    default_load: float = 0.7,
) -> nx.DiGraph:
    """Add `risk` (probability) and `risk_level` (Low/Med/High) to every edge.

    Uses the trained ML model under average conditions, so the graph carries
    the ML signal even before the user asks for a specific prediction.
    """
    # Imported lazily to keep graph_builder importable before the model exists
    from services.prediction_service import predict_delay

    for _, _, d in G.edges(data=True):
        r = predict_delay(
            distance_km=d["distance"],
            weather_score=default_weather,
            traffic_score=default_traffic,
            warehouse_load=default_load,
            hist_avg_delay_hrs=d["hist_delay"],
            transport_mode=int(d.get("transport_mode", 0)),
        )
        d["risk"] = r["delay_probability"]
        d["risk_level"] = r["risk_level"]
    return G
