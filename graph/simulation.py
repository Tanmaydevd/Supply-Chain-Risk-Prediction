"""Cascading-failure simulation aligned with the paper:

'Real-Time Prediction of Delivery Delay in Supply Chains using ML Approaches'
(Kup et al., Kadir Has University / HepsiJet)

Key improvements over naive node-removal:
  1. WCC-based isolation — a node is isolated if it is in a weakly-connected
     component SEPARATE from the main network, not just if its degree == 0.
  2. True cascading — after isolated nodes are removed, the process repeats
     until the network stabilises (no new isolations appear).
  3. Risk-impact scoring — delay probabilities on surviving routes are
     re-evaluated under increased load (rerouted traffic raises warehouse_load)
     and the delta vs. the pre-failure state is returned for display.
"""
from __future__ import annotations
import networkx as nx


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _main_component(H: nx.DiGraph) -> set[str]:
    """Return the node-set of the largest weakly-connected component."""
    if H.number_of_nodes() == 0:
        return set()
    wccs = list(nx.weakly_connected_components(H))
    return max(wccs, key=len)


def _newly_isolated(H: nx.DiGraph) -> list[str]:
    """Nodes NOT in the main weakly-connected component."""
    if H.number_of_nodes() == 0:
        return []
    main = _main_component(H)
    return [n for n in H.nodes if n not in main]


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def cascade_failure(G: nx.DiGraph, failed_node: str) -> dict:
    """Simulate cascading failure starting from `failed_node`.

    Algorithm (iterative until stable):
      1. Remove `failed_node` and record its edges as affected routes.
      2. Find all nodes now isolated from the main WCC.
      3. Remove those isolated nodes (they too propagate failures).
      4. Repeat until no new isolations appear.

    Returns:
        {
          "failed_node": str,
          "cascade_order": list[str],   # order in which nodes were removed
          "lost_edges": int,
          "affected_routes": list[(u, v)],
          "isolated_nodes": list[str],  # all nodes removed in cascade
          "remaining_nodes": int,
          "remaining_edges": int,
          "wcc_count": int,             # weakly-connected components BEFORE cascade
        }
    """
    if failed_node not in G:
        raise ValueError(f"Unknown node: {failed_node}")

    H = G.copy()
    cascade_order: list[str] = []
    affected_routes: list[tuple[str, str]] = []

    # Step 1 — remove the primary failure
    affected_routes += list(H.in_edges(failed_node)) + list(H.out_edges(failed_node))
    H.remove_node(failed_node)
    cascade_order.append(failed_node)

    # Step 2+ — cascade until stable
    while True:
        isolated = _newly_isolated(H)
        if not isolated:
            break
        for node in isolated:
            if node in H:
                affected_routes += list(H.in_edges(node)) + list(H.out_edges(node))
                H.remove_node(node)
                cascade_order.append(node)

    secondary = [n for n in cascade_order if n != failed_node]

    return {
        "failed_node": failed_node,
        "cascade_order": cascade_order,
        "secondary_failures": secondary,
        "lost_edges": G.number_of_edges() - H.number_of_edges(),
        "affected_routes": list(set(affected_routes)),
        "isolated_nodes": secondary,      # keep old key for UI compat
        "remaining_nodes": H.number_of_nodes(),
        "remaining_edges": H.number_of_edges(),
        "wcc_count": len(list(nx.weakly_connected_components(G))),
        "surviving_graph": H,
    }


def risk_impact(
    G_before: nx.DiGraph,
    G_after: nx.DiGraph,
    load_increase: float = 0.15,
) -> list[dict]:
    """Compare delay-risk on edges that survive the failure.

    When a hub is removed, surviving routes carry more traffic.
    We model this as warehouse_load += load_increase on all surviving edges.

    Returns a list of dicts (one per surviving edge) with before/after risk.
    """
    from services.prediction_service import predict_delay

    rows = []
    for u, v, d in G_after.edges(data=True):
        before = G_before[u][v]["risk"] if G_before.has_edge(u, v) else None
        r_after = predict_delay(
            distance_km=d.get("distance", 500),
            weather_score=1,
            traffic_score=1,
            warehouse_load=min(d.get("load", 0.7) + load_increase, 1.0),
            hist_avg_delay_hrs=d.get("hist_delay", 3.0),
        )
        rows.append({
            "route": f"{u} -> {v}",
            "origin": u,
            "destination": v,
            "risk_before": round(before, 3) if before is not None else None,
            "risk_after": round(r_after["delay_probability"], 3),
            "delta": round(r_after["delay_probability"] - (before or 0), 3),
            "risk_level_after": r_after["risk_level"],
        })

    return sorted(rows, key=lambda r: -(r["delta"] or 0))
