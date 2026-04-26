"""Load trained model and expose predict_delay() with full 9-feature set."""
from __future__ import annotations
import joblib
import pandas as pd

from config import MODELS_DIR, RISK_THRESHOLDS
from ml.preprocess import feature_columns

_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        path = MODELS_DIR / "delay_rf.joblib"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Run `python run_pipeline.py` first."
            )
        _MODEL = joblib.load(path)
        if hasattr(_MODEL, "n_jobs"):
            _MODEL.n_jobs = 1
    return _MODEL


def _bucket(p: float) -> str:
    if p >= RISK_THRESHOLDS["medium"]: return "High"
    if p >= RISK_THRESHOLDS["low"]:   return "Medium"
    return "Low"


def predict_delay(
    distance_km:        float,
    weather_score:      int   = 1,
    traffic_score:      int   = 1,
    warehouse_load:     float = 0.70,
    hist_avg_delay_hrs: float = 3.0,
    transport_mode:     int   = 0,    # 0=road 1=sea 2=air
    port_congestion:    float = 0.20,
    vessel_delay_hrs:   float = 0.0,
    flight_delay_min:   float = 0.0,
) -> dict:
    """Return delay probability, risk score (0-100), and risk level."""
    m = _model()
    feats = feature_columns()
    vals  = [distance_km, weather_score, traffic_score,
             warehouse_load, hist_avg_delay_hrs,
             transport_mode, port_congestion,
             vessel_delay_hrs, flight_delay_min]
    # handle models trained on old 5-feature set (backward compat)
    x = pd.DataFrame([vals[:len(feats)]], columns=feats)
    p = float(m.predict_proba(x)[0, 1])
    return {
        "delay_probability": round(p, 3),
        "risk_score":        int(round(p * 100)),
        "risk_level":        _bucket(p),
    }
