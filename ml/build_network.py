"""Build the comprehensive India logistics network.

52 nodes:
  - 28 major warehouses / fulfillment centres / 3PL hubs
  - 14 major seaports
  - 10 major cargo airports

Edges are auto-computed using haversine distance + transport-mode logic:
  road  (0) — warehouse ↔ warehouse, warehouse ↔ port, warehouse ↔ airport
  sea   (1) — port ↔ port (coastal lanes)
  air   (2) — airport ↔ airport

Run:  python -m ml.build_network
"""
from __future__ import annotations
import math
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "data" / "processed"

# ── Node definitions ──────────────────────────────────────────────────────────
NODES = [
    # ── Warehouses / Fulfillment Centres / 3PL hubs ──────────────────────────
    # name, lat, lon, type, subtype
    ("Amazon FC Bhiwandi",        19.2967,  73.0593, "warehouse", "fc"),
    ("Flipkart FC Bhiwandi",      19.3100,  73.0650, "warehouse", "fc"),
    ("Amazon FC Manesar",         28.3500,  76.9300, "warehouse", "fc"),
    ("Delhivery Hub Gurgaon",     28.4595,  77.0266, "warehouse", "3pl"),
    ("Amazon FC Noida",           28.5355,  77.3910, "warehouse", "fc"),
    ("Flipkart FC Bangalore",     12.8389,  77.6627, "warehouse", "fc"),
    ("Amazon FC Bangalore",       12.9120,  77.6500, "warehouse", "fc"),
    ("Amazon FC Hyderabad",       17.4126,  78.4072, "warehouse", "fc"),
    ("Amazon FC Chennai",         12.9824,  80.2181, "warehouse", "fc"),
    ("Amazon FC Kolkata",         22.6328,  88.3793, "warehouse", "fc"),
    ("XpressBees Hub Pune",       18.6526,  73.8524, "warehouse", "3pl"),
    ("Delhivery Hub Jaipur",      26.8935,  75.7568, "warehouse", "3pl"),
    ("Ecom Express Lucknow",      26.8701,  80.9462, "warehouse", "3pl"),
    ("Blue Dart Hub Ahmedabad",   23.0653,  72.5897, "warehouse", "3pl"),
    ("Amazon FC Surat",           21.1702,  72.8311, "warehouse", "fc"),
    ("Mahindra Logistics Nagpur", 21.0762,  79.0415, "warehouse", "3pl"),
    ("Delhivery Hub Coimbatore",  11.0168,  76.9558, "warehouse", "3pl"),
    ("Amazon FC Kochi",           10.0227,  76.3267, "warehouse", "fc"),
    ("Amazon FC Visakhapatnam",   17.7231,  83.3012, "warehouse", "fc"),
    ("Ludhiana Industrial Hub",   30.9010,  75.8573, "warehouse", "industrial"),
    ("Panipat Textile Hub",       29.3909,  76.9635, "warehouse", "industrial"),
    ("Tiruppur Textile Hub",      11.1085,  77.3411, "warehouse", "industrial"),
    ("Rajkot Industrial Hub",     22.3039,  70.8022, "warehouse", "industrial"),
    ("Blue Dart Hub Indore",      22.7196,  75.8577, "warehouse", "3pl"),
    ("Delhivery Hub Patna",       25.5941,  85.1376, "warehouse", "3pl"),
    ("WCI Bhubaneswar",           20.2961,  85.8245, "warehouse", "3pl"),
    ("Amazon FC Chandigarh",      30.7333,  76.7794, "warehouse", "fc"),
    ("Flipkart Hub Vadodara",     22.3072,  73.1812, "warehouse", "fc"),

    # ── Major Seaports ────────────────────────────────────────────────────────
    ("JNPT Port",                 18.9500,  72.9333, "port", "seaport"),
    ("Mumbai Port",               18.9220,  72.8347, "port", "seaport"),
    ("Kandla Port",               22.9500,  70.2000, "port", "seaport"),
    ("Mundra Port",               22.8395,  69.7060, "port", "seaport"),
    ("Chennai Port",              13.0900,  80.2900, "port", "seaport"),
    ("Ennore Port",               13.2167,  80.3167, "port", "seaport"),
    ("Visakhapatnam Port",        17.6932,  83.2771, "port", "seaport"),
    ("Paradip Port",              20.3167,  86.6167, "port", "seaport"),
    ("Kolkata Port",              22.5800,  88.3200, "port", "seaport"),
    ("Haldia Port",               22.0621,  88.0684, "port", "seaport"),
    ("Kochi Port",                 9.9667,  76.2667, "port", "seaport"),
    ("New Mangalore Port",        12.9201,  74.8100, "port", "seaport"),
    ("Mormugao Port",             15.4000,  73.8000, "port", "seaport"),
    ("Tuticorin Port",             8.7642,  78.1348, "port", "seaport"),

    # ── Major Cargo Airports ──────────────────────────────────────────────────
    ("Mumbai Airport BOM",        19.0896,  72.8656, "airport", "cargo"),
    ("Delhi Airport DEL",         28.5665,  77.1031, "airport", "cargo"),
    ("Bangalore Airport BLR",     13.1986,  77.7066, "airport", "cargo"),
    ("Chennai Airport MAA",       12.9941,  80.1709, "airport", "cargo"),
    ("Kolkata Airport CCU",       22.6520,  88.4463, "airport", "cargo"),
    ("Hyderabad Airport HYD",     17.2403,  78.4294, "airport", "cargo"),
    ("Ahmedabad Airport AMD",     23.0772,  72.6347, "airport", "cargo"),
    ("Kochi Airport COK",         10.1520,  76.4019, "airport", "cargo"),
    ("Pune Airport PNQ",          18.5822,  73.9197, "airport", "cargo"),
    ("Nagpur Airport NAG",        21.0922,  79.0472, "airport", "cargo"),
]


# ── Haversine distance (km) ────────────────────────────────────────────────────
def _dist(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Historical delay lookup (hrs per km, by mode) ─────────────────────────────
_DELAY_PER_KM = {"road": 0.006, "sea": 0.003, "air": 0.0008}
_SPEED_KMH    = {"road": 55,    "sea": 22,    "air": 700}


def _hist_delay(dist_km: float, mode: str) -> float:
    base = dist_km / _SPEED_KMH[mode]   # travel time hrs
    return round(base * (1 + _DELAY_PER_KM[mode] * 10), 2)


# ── Edge generation rules ──────────────────────────────────────────────────────
def _build_edges(nodes_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    n = len(nodes_df)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            a = nodes_df.iloc[i]
            b = nodes_df.iloc[j]
            at, bt = a["type"], b["type"]
            dist = _dist(a.lat, a.lon, b.lat, b.lon)

            mode = None

            # warehouse ↔ warehouse : road, max 700 km
            if at == "warehouse" and bt == "warehouse" and dist <= 700:
                mode = "road"

            # warehouse ↔ port : road, max 200 km
            elif at == "warehouse" and bt == "port" and dist <= 200:
                mode = "road"
            elif at == "port" and bt == "warehouse" and dist <= 200:
                mode = "road"

            # warehouse ↔ airport : road, max 80 km
            elif at == "warehouse" and bt == "airport" and dist <= 80:
                mode = "road"
            elif at == "airport" and bt == "warehouse" and dist <= 80:
                mode = "road"

            # port ↔ port : sea, all coastal connections
            elif at == "port" and bt == "port" and dist <= 3000:
                mode = "sea"

            # airport ↔ airport : air, all major connections
            elif at == "airport" and bt == "airport":
                mode = "air"

            # port ↔ airport : road (ground transport between port & airport)
            elif at == "port" and bt == "airport" and dist <= 60:
                mode = "road"
            elif at == "airport" and bt == "port" and dist <= 60:
                mode = "road"

            if mode:
                delay = _hist_delay(dist, mode)
                rows.append({
                    "origin":            a["name"],
                    "destination":       b["name"],
                    "distance_km":       round(dist, 1),
                    "hist_avg_delay_hrs": delay,
                    "transport_mode":    {"road": 0, "sea": 1, "air": 2}[mode],
                    "mode_label":        mode,
                })

    return pd.DataFrame(rows)


def build_and_save():
    OUT.mkdir(parents=True, exist_ok=True)

    # nodes
    nodes_df = pd.DataFrame(NODES, columns=["name", "lat", "lon", "type", "subtype"])
    nodes_path = OUT / "nodes.csv"
    nodes_df.to_csv(nodes_path, index=False)
    print(f"[network] wrote {len(nodes_df)} nodes -> {nodes_path}")

    # edges
    edges_df = _build_edges(nodes_df)
    edges_path = OUT / "edges.csv"
    edges_df.to_csv(edges_path, index=False)
    print(f"[network] wrote {len(edges_df)} edges -> {edges_path}")

    # summary
    for t in ["warehouse","port","airport"]:
        cnt = (nodes_df.type == t).sum()
        print(f"  {t:10s}: {cnt} nodes")
    for m in ["road","sea","air"]:
        cnt = (edges_df.mode_label == m).sum()
        print(f"  {m:6s} edges: {cnt}")

    return nodes_df, edges_df


if __name__ == "__main__":
    build_and_save()
