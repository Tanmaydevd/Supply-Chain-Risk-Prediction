"""Centrality + bottleneck analytics on the supply-chain graph."""
from __future__ import annotations
import networkx as nx


def centrality(G: nx.DiGraph) -> dict:
    return {
        "degree": nx.degree_centrality(G),
        "betweenness": nx.betweenness_centrality(G, weight="distance"),
        "closeness": nx.closeness_centrality(G, distance="distance"),
    }


def critical_hubs(G: nx.DiGraph, top_n: int = 5) -> list[tuple[str, float]]:
    bc = nx.betweenness_centrality(G, weight="distance")
    return sorted(bc.items(), key=lambda kv: kv[1], reverse=True)[:top_n]


def bottleneck_edges(G: nx.DiGraph, top_n: int = 5):
    eb = nx.edge_betweenness_centrality(G, weight="distance")
    return sorted(eb.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
