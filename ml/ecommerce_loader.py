"""Load the E-Commerce Shipping Dataset (real shipment data with delay labels).

Dataset: "E-Commerce Shipping Dataset" by Prachi Gopalani
Source:  https://www.kaggle.com/datasets/prachi13/customer-analytics
Rows:    ~10,999 real shipments from an international e-commerce company
Target:  Reached.on.Time_Y.N  (1 = delayed, 0 = on time)

HOW TO DOWNLOAD (one-time setup):
  Option A — Kaggle CLI (recommended):
    1. Install:  pip install kaggle
    2. Create API token at https://www.kaggle.com/settings -> API -> Create New Token
    3. Save the downloaded kaggle.json to  C:/Users/<you>/.kaggle/kaggle.json
    4. Run:  python -m ml.ecommerce_loader --download

  Option B — Manual:
    1. Visit https://www.kaggle.com/datasets/prachi13/customer-analytics
    2. Download and unzip
    3. Copy "Train.csv" or "E Commerce.csv" to  data/raw/ecommerce/

Feature mapping to our model schema:
  Warehouse_block (A-F) -> origin city
  Mode_of_Shipment      -> destination category (port / hub / nearby)
  Weight_in_gms         -> warehouse_load  (normalised 0.3-1.0)
  Customer_care_calls   -> hist_avg_delay_hrs  (2 hrs * calls)
  distance_km           -> looked up from our edges table (origin, destination)
  weather_score         -> 0 at training time (overridden by live API at inference)
  traffic_score         -> 0 at training time (overridden by live API at inference)
  delayed               -> Reached.on.Time_Y.N
"""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path

import pandas as pd

from config import DATA_PROCESSED, DATA_RAW
from ml.preprocess import load_edges, load_nodes

ECOM_DIR = DATA_RAW / "ecommerce"
ECOM_CSV = ECOM_DIR / "E Commerce.csv"
ECOM_CSV_CANDIDATES = [
    ECOM_DIR / "E Commerce.csv",
    ECOM_DIR / "Train.csv",
    ECOM_DIR / "train.csv",
]

# Warehouse block -> origin city (deterministic, documented)
_BLOCK_TO_CITY: dict[str, str] = {
    "A": "Mumbai",
    "B": "Delhi",
    "C": "Bangalore",
    "D": "Hyderabad",
    "E": "Chennai",
    "F": "Kolkata",
}

# Mode -> destination pool (city types to prefer)
_MODE_CITY_POOLS: dict[str, list[str]] = {
    "Ship":   ["Kochi", "Visakhapatnam", "Chennai", "Mumbai", "Kolkata"],
    "Flight": ["Delhi", "Bangalore", "Hyderabad", "Mumbai", "Chennai"],
    "Road":   ["Pune", "Ahmedabad", "Bhopal", "Nagpur", "Jaipur", "Lucknow"],
}


def _hash_destination(row_id: int, mode: str, all_cities: list[str]) -> str:
    pool = _MODE_CITY_POOLS.get(mode, all_cities)
    key = f"{row_id}:{mode}"
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return pool[h % len(pool)]


def _lookup_distance(origin: str, destination: str, edges: pd.DataFrame) -> float:
    match = edges[(edges.origin == origin) & (edges.destination == destination)]
    if not match.empty:
        return float(match.iloc[0].distance_km)
    # no direct edge: use median distance as a neutral fallback
    return float(edges.distance_km.median())


def _lookup_hist_delay(origin: str, destination: str, edges: pd.DataFrame) -> float:
    match = edges[(edges.origin == origin) & (edges.destination == destination)]
    if not match.empty:
        return float(match.iloc[0].hist_avg_delay_hrs)
    return float(edges.hist_avg_delay_hrs.median())


def download_dataset() -> None:
    """Attempt to download via Kaggle CLI. Requires kaggle.json credentials."""
    try:
        import kaggle  # noqa: F401
    except ImportError:
        print("[ecommerce] Install kaggle:  pip install kaggle")
        sys.exit(1)

    ECOM_DIR.mkdir(parents=True, exist_ok=True)
    import subprocess
    print("[ecommerce] Downloading via Kaggle API...")
    result = subprocess.run(
        [
            sys.executable, "-m", "kaggle", "datasets", "download",
            "-d", "prachi13/customer-analytics",
            "--path", str(ECOM_DIR),
            "--unzip",
        ],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)
    print(f"[ecommerce] Dataset saved to {ECOM_DIR}")


def _find_ecommerce_csv() -> Path:
    for path in ECOM_CSV_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        f"No e-commerce CSV found in {ECOM_DIR}.\n"
        "Expected one of: E Commerce.csv, Train.csv, train.csv\n"
        "Run:  python -m ml.ecommerce_loader --download\n"
        "Or download manually from https://www.kaggle.com/datasets/prachi13/customer-analytics"
    )


def load_ecommerce() -> pd.DataFrame:
    """Load the E-Commerce Shipping Dataset and return a model-compatible DataFrame."""
    csv_path = _find_ecommerce_csv()
    raw = pd.read_csv(csv_path)
    print(f"[ecommerce] Loaded {len(raw):,} rows from {csv_path.name}")

    edges = load_edges()
    from ml.preprocess import get_node_names
    all_cities = get_node_names()

    rows = []
    for idx, row in raw.iterrows():
        block = str(row.get("Warehouse_block", "A")).strip().upper()
        mode = str(row.get("Mode_of_Shipment", "Road")).strip()
        weight = float(row.get("Weight_in_gms", 3000))
        calls = int(row.get("Customer_care_calls", 2))
        reached = int(row.get("Reached.on.Time_Y.N", 1))

        origin = _BLOCK_TO_CITY.get(block, "Mumbai")
        destination = _hash_destination(int(idx), mode, all_cities)

        # avoid same-city shipments
        if destination == origin:
            pool = [c for c in all_cities if c != origin]
            h = int(hashlib.md5(f"{idx}:fallback".encode()).hexdigest(), 16)
            destination = pool[h % len(pool)]

        # normalise weight to warehouse_load (1000g -> 0.3, 7000g -> 1.0)
        wh_load = round(0.3 + (min(max(weight, 1000), 7000) - 1000) / (7000 - 1000) * 0.7, 3)

        # customer care calls as proxy for historical delay severity
        hist_delay = round(float(calls) * 2.0, 1)

        rows.append({
            "origin":            origin,
            "destination":       destination,
            "distance_km":       _lookup_distance(origin, destination, edges),
            "weather_score":     0,   # neutral at train time; replaced by live API at inference
            "traffic_score":     0,   # neutral at train time; replaced by live API at inference
            "warehouse_load":    wh_load,
            "hist_avg_delay_hrs": hist_delay,
            "delayed":           reached,   # Kaggle: 1=not reached on time
        })

    df = pd.DataFrame(rows)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "ecommerce_shipments.csv"
    df.to_csv(out_path, index=False)
    print(f"[ecommerce] wrote {len(df):,} rows -> {out_path}")
    print(f"[ecommerce] delay rate = {df['delayed'].mean():.1%}")
    return df


def merge_with_synthetic() -> pd.DataFrame:
    """Append real e-commerce shipments to the synthetic set and retrain."""
    syn_path = DATA_PROCESSED / "shipments.csv"
    ecom_path = DATA_PROCESSED / "ecommerce_shipments.csv"
    if not syn_path.exists():
        raise FileNotFoundError("Run python -m ml.preprocess first.")
    if not ecom_path.exists():
        raise FileNotFoundError("Run python -m ml.ecommerce_loader first.")
    merged = pd.concat(
        [pd.read_csv(syn_path), pd.read_csv(ecom_path)],
        ignore_index=True,
    )
    merged.to_csv(syn_path, index=False)
    print(f"[ecommerce] merged -> {syn_path}  ({len(merged):,} total rows)")
    return merged


if __name__ == "__main__":
    if "--download" in sys.argv:
        download_dataset()
    load_ecommerce()
