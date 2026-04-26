"""Optional: ingest Olist e-commerce shipment data for richer training.

Olist dataset (Kaggle: olistbr/brazilian-ecommerce):
    - olist_orders_dataset.csv
    - olist_order_items_dataset.csv
    - olist_customers_dataset.csv
    - olist_sellers_dataset.csv

Usage:
    1. Download CSVs into data/raw/olist/
    2. Run: python -m ml.olist_loader
    3. It will produce data/processed/olist_shipments.csv with columns
       compatible with our pipeline.

Notes:
    - Olist cities are Brazilian — they won't match our 15-city Indian graph.
      For demo, we map Olist cities to our hubs by string hashing
      (deterministic but synthetic). This is purely to "stress-test" the
      pipeline with more rows; it does NOT add real geographic accuracy.
    - In a serious production setting you'd build a separate Brazilian graph.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

import pandas as pd

from config import DATA_PROCESSED, DATA_RAW
from ml.preprocess import load_nodes


OLIST_DIR = DATA_RAW / "olist"


def _hash_to_city(value: str, cities: list[str]) -> str:
    """Deterministically hash a Brazilian city name to one of our 15 cities."""
    h = int(hashlib.md5(value.encode("utf-8")).hexdigest(), 16)
    return cities[h % len(cities)]


def load_olist() -> pd.DataFrame:
    """Build a shipments-shaped DataFrame from Olist data."""
    orders = pd.read_csv(OLIST_DIR / "olist_orders_dataset.csv")
    items = pd.read_csv(OLIST_DIR / "olist_order_items_dataset.csv")
    customers = pd.read_csv(OLIST_DIR / "olist_customers_dataset.csv")
    sellers = pd.read_csv(OLIST_DIR / "olist_sellers_dataset.csv")

    # join: order -> first item -> seller + customer
    df = (
        items.groupby("order_id").first().reset_index()
        .merge(orders[[
            "order_id", "order_purchase_timestamp",
            "order_delivered_customer_date",
            "order_estimated_delivery_date"
        ]], on="order_id", how="inner")
        .merge(sellers[["seller_id", "seller_city"]], on="seller_id", how="left")
        .merge(customers[["customer_id", "customer_city"]],
               on="customer_id", how="left")
    )

    # delayed = delivered after estimated date
    df["order_delivered_customer_date"] = pd.to_datetime(
        df["order_delivered_customer_date"], errors="coerce"
    )
    df["order_estimated_delivery_date"] = pd.to_datetime(
        df["order_estimated_delivery_date"], errors="coerce"
    )
    df = df.dropna(subset=[
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
        "seller_city", "customer_city",
    ])
    df["delayed"] = (
        df["order_delivered_customer_date"] > df["order_estimated_delivery_date"]
    ).astype(int)

    # map Olist cities to our 15-city graph (synthetic; documented above)
    from ml.preprocess import get_node_names
    cities = get_node_names()
    df["origin"] = df["seller_city"].apply(lambda v: _hash_to_city(v, cities))
    df["destination"] = df["customer_city"].apply(lambda v: _hash_to_city(v, cities))
    df = df[df["origin"] != df["destination"]]

    # synthesize features the model expects (Olist doesn't have weather/traffic)
    rng_seed = 7
    rng = pd.Series(range(len(df))).apply(
        lambda i: ((i * 9301 + 49297 + rng_seed) % 233280) / 233280.0
    ).values
    df["weather_score"] = ((rng * 3) // 1).astype(int).clip(0, 2)
    df["traffic_score"] = (((rng * 7) % 3) // 1).astype(int).clip(0, 2)
    df["warehouse_load"] = (rng * 0.7 + 0.3).round(3)
    df["distance_km"] = (df["price"].astype(float) % 1500 + 100).round(0) \
        if "price" in df.columns else 500.0
    df["hist_avg_delay_hrs"] = ((rng * 8) + 1).round(1)

    keep = [
        "origin", "destination", "distance_km", "weather_score",
        "traffic_score", "warehouse_load", "hist_avg_delay_hrs", "delayed",
    ]
    out = df[keep].copy()

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "olist_shipments.csv"
    out.to_csv(out_path, index=False)
    print(f"[olist] {len(out):,} rows -> {out_path}")
    print(f"[olist] delay rate = {out['delayed'].mean():.1%}")
    return out


def merge_with_synthetic() -> pd.DataFrame:
    """Append Olist shipments to our synthetic ones for richer training."""
    syn = pd.read_csv(DATA_PROCESSED / "shipments.csv")
    olist = pd.read_csv(DATA_PROCESSED / "olist_shipments.csv")
    merged = pd.concat([syn, olist], ignore_index=True)
    out = DATA_PROCESSED / "shipments.csv"
    merged.to_csv(out, index=False)
    print(f"[olist] merged -> {out}  ({len(merged):,} total rows)")
    return merged


if __name__ == "__main__":
    if not OLIST_DIR.exists():
        print(
            f"Olist data not found at {OLIST_DIR}.\n"
            "Download from https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce\n"
            "and unzip into that folder."
        )
    else:
        load_olist()
        # uncomment if you want to merge automatically:
        # merge_with_synthetic()
