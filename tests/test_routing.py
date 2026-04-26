import pytest


def test_alternate_route_exists():
    """Requires trained model — skip cleanly if not yet trained."""
    pytest.importorskip("joblib")
    try:
        from services.routing_service import best_route
        r = best_route("Bangalore", "Chennai")
    except FileNotFoundError:
        pytest.skip("Model not trained yet — run `python -m ml.train_model`.")
    assert r["path"] is not None
    assert r["path"][0] == "Bangalore"
    assert r["path"][-1] == "Chennai"
