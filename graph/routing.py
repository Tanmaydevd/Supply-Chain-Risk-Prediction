"""Alternate-route recommendation via shortest-path on risk-weighted graph."""
from __future__ import annotations
import networkx as nx


def suggest_alternate(
    G: nx.DiGraph,
    origin: str,
    destination: str,
    avoid_node: str | None = None,
    weight: str = "risk",
) -> dict:
    """Return the lowest-`weight` path from origin -> destination.

    If `avoid_node` is provided, that node is excluded.
    """
    H = G.copy()
    if avoid_node and avoid_node in H:
        H.remove_node(avoid_node)
    try:
        path = nx.shortest_path(H, origin, destination, weight=weight)
        cost = nx.shortest_path_length(H, origin, destination, weight=weight)
        # also compute total distance along the suggested path
        dist = sum(
            H[u][v]["distance"] for u, v in zip(path[:-1], path[1:])
        )
        return {
            "path": path,
            "total_risk": round(float(cost), 3),
            "total_distance_km": round(dist, 1),
            "hops": len(path) - 1,
        }
    except nx.NetworkXNoPath:
        return {"path": None, "total_risk": None,
                "total_distance_km": None, "hops": None}
    except nx.NodeNotFound as e:
        return {"path": None, "error": str(e)}
