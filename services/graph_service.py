"""Glue layer between Streamlit pages and graph/* modules."""
from __future__ import annotations
import networkx as nx

from graph.graph_builder import build_graph, annotate_with_risk
from graph.analytics import critical_hubs

_G: nx.DiGraph | None = None


def get_annotated_graph() -> nx.DiGraph:
    """Build + annotate the graph once; cache for the lifetime of the process."""
    global _G
    if _G is None:
        _G = annotate_with_risk(build_graph())
    return _G


def reset_cache() -> None:
    global _G
    _G = None


def all_nodes() -> list[str]:
    return list(get_annotated_graph().nodes)


def overview_metrics() -> dict:
    G = get_annotated_graph()
    risks = [d["risk"] for _, _, d in G.edges(data=True)]
    return {
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "avg_risk": (sum(risks) / len(risks)) if risks else 0.0,
        "n_critical": len(critical_hubs(G, 5)),
    }
