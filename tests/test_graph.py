def test_graph_builds_with_all_nodes():
    from graph.graph_builder import build_graph
    G = build_graph()
    assert G.number_of_nodes() >= 10
    assert G.number_of_edges() > 0
    # every node has lat/lon
    for n, d in G.nodes(data=True):
        assert "lat" in d and "lon" in d


def test_cascade_failure_removes_node():
    from graph.graph_builder import build_graph
    from graph.simulation import cascade_failure
    G = build_graph()
    target = "Chennai"
    res = cascade_failure(G, target)
    assert res["failed_node"] == target
    assert res["lost_edges"] >= 1
    assert res["remaining_nodes"] == G.number_of_nodes() - 1
