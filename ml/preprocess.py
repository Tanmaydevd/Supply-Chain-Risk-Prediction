"""Data preprocessing — extended feature set covering road, sea, and air modes.

New features vs. original:
  transport_mode   int   0=road 1=sea 2=air
  port_congestion  float 0-1   congestion at nearest port
  vessel_delay_hrs float 0-20  expected sea-leg delay
  flight_delay_min float 0-120 expected air-leg delay

Run:  python -m ml.preprocess
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from config import DATA_PROCESSED, N_SYNTHETIC_SHIPMENTS, RANDOM_SEED


def feature_columns() -> list[str]:
    """All features used for training and inference (order matters)."""
    return [
        "distance_km",
        "weather_score",
        "traffic_score",
        "warehouse_load",
        "hist_avg_delay_hrs",
        "transport_mode",      # 0=road 1=sea 2=air
        "port_congestion",     # 0.0-1.0
        "vessel_delay_hrs",    # 0-20 (sea mode only, 0 otherwise)
        "flight_delay_min",    # 0-120 (air mode only, 0 otherwise)
    ]


def load_nodes() -> pd.DataFrame:
    df = pd.read_csv(DATA_PROCESSED / "nodes.csv")
    # normalise: old schema has "city", new schema has "name" — expose both
    if "name" in df.columns and "city" not in df.columns:
        df["city"] = df["name"]
    elif "city" in df.columns and "name" not in df.columns:
        df["name"] = df["city"]
    return df


def get_node_names() -> list[str]:
    """Return list of all node names regardless of schema version."""
    df = load_nodes()
    return df["name"].tolist() if "name" in df.columns else df["city"].tolist()


def load_edges() -> pd.DataFrame:
    df = pd.read_csv(DATA_PROCESSED / "edges.csv")
    # ensure transport_mode column exists (backward compat with old edges.csv)
    if "transport_mode" not in df.columns:
        df["transport_mode"] = 0
    return df


def generate_synthetic_shipments(
    n: int = N_SYNTHETIC_SHIPMENTS,
    seed: int = RANDOM_SEED,
    label_noise: float = 0.08,
) -> pd.DataFrame:
    """Generate n synthetic shipments across road / sea / air modes.

    Delay rule (ground truth, never seen by model):
      base       = 0.05
      + weather  : +0.12 * score (0-2)
      + traffic  : +0.18 * score (road only)
      + load     : +0.25 * max(0, load-0.70)
      + mode     : sea +0.08 / air +0.03 / road +0.0
      + port     : +0.20 * port_congestion (sea/air)
      + vessel   : +0.04 * vessel_delay_hrs / 10
      + flight   : +0.03 * flight_delay_min / 60
    """
    rng = np.random.default_rng(seed)
    edges = load_edges()
    rows = []

    for _ in range(n):
        e = edges.iloc[int(rng.integers(0, len(edges)))]
        mode    = int(e.get("transport_mode", 0))
        weather = int(rng.choice([0, 1, 2], p=[0.6, 0.3, 0.1]))
        traffic = int(rng.choice([0, 1, 2], p=[0.5, 0.35, 0.15])) if mode == 0 else 0
        wh_load = float(rng.uniform(0.3, 1.0))

        # mode-specific extras
        port_cong    = float(rng.uniform(0.1, 0.9)) if mode in (1, 2) else float(rng.uniform(0.0, 0.3))
        vessel_delay = float(rng.uniform(0, 18))    if mode == 1 else 0.0
        flight_delay = float(rng.uniform(0, 90))    if mode == 2 else 0.0

        p = (0.05
             + 0.12 * weather
             + 0.18 * traffic
             + 0.25 * max(0.0, wh_load - 0.70)
             + {0: 0.0, 1: 0.08, 2: 0.03}[mode]
             + 0.20 * port_cong
             + 0.04 * (vessel_delay / 10)
             + 0.03 * (flight_delay / 60))
        p = min(p, 0.95)
        delayed = int(rng.random() < p)
        if rng.random() < label_noise:
            delayed = 1 - delayed

        rows.append({
            "origin":            e.origin,
            "destination":       e.destination,
            "distance_km":       float(e.distance_km),
            "weather_score":     weather,
            "traffic_score":     traffic,
            "warehouse_load":    round(wh_load, 3),
            "hist_avg_delay_hrs": float(e.hist_avg_delay_hrs),
            "transport_mode":    mode,
            "port_congestion":   round(port_cong, 3),
            "vessel_delay_hrs":  round(vessel_delay, 2),
            "flight_delay_min":  round(flight_delay, 1),
            "delayed":           delayed,
        })

    df = pd.DataFrame(rows)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out = DATA_PROCESSED / "shipments.csv"
    df.to_csv(out, index=False)
    print(f"[preprocess] wrote {len(df):,} rows -> {out}")
    print(f"[preprocess] delay rate = {df['delayed'].mean():.1%}")
    mode_labels = {0:"road", 1:"sea", 2:"air"}
    for m, lbl in mode_labels.items():
        sub = df[df.transport_mode == m]
        if len(sub):
            print(f"[preprocess]   {lbl:4s}: {len(sub):,} rows  "
                  f"delay={sub['delayed'].mean():.1%}")
    return df


if __name__ == "__main__":
    generate_synthetic_shipments()
