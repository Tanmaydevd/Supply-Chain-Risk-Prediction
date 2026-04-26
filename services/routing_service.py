"""Decision-support facade: best route + alternate route."""
from __future__ import annotations
from graph.routing import suggest_alternate
from services.graph_service import get_annotated_graph


def best_route(origin: str, destination: str) -> dict:
    G = get_annotated_graph()
    return suggest_alternate(G, origin, destination, weight="risk")


def alternate_avoiding(origin: str, destination: str, avoid_node: str) -> dict:
    G = get_annotated_graph()
    return suggest_alternate(G, origin, destination,
                             avoid_node=avoid_node, weight="risk")
