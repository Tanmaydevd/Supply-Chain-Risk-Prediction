def test_synthetic_shipments_has_label():
    from ml.preprocess import generate_synthetic_shipments
    df = generate_synthetic_shipments(n=200, seed=0)
    assert "delayed" in df.columns
    assert df["delayed"].nunique() == 2
    assert len(df) == 200


def test_feature_columns_consistent():
    from ml.preprocess import feature_columns
    cols = feature_columns()
    assert "distance_km" in cols
    assert "weather_score" in cols
    assert "traffic_score" in cols
