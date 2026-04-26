"""Real-time weather via Open-Meteo API.

Completely free — no API key, no registration.
Docs: https://open-meteo.com/en/docs

Coordinate resolution priority:
  1. nodes.csv  (exact node name → lat/lon from the live network data)
  2. CITY_COORDS dict in config.py  (legacy city names)
  3. Partial-match: extract city name embedded in node name

WMO code mapping:
  0-3      -> Sunny / Cloudy  (score 0)
  45,48    -> Fog              (score 1)
  51-82    -> Rain / Drizzle   (score 1)
  85,86    -> Snow showers     (score 1)
  95-99    -> Thunderstorm     (score 2)
"""
from __future__ import annotations
import requests
from pathlib import Path
from functools import lru_cache

_BASE_URL = "https://api.open-meteo.com/v1/forecast"
_NODES_CSV = Path(__file__).resolve().parent.parent / "data" / "processed" / "nodes.csv"


@lru_cache(maxsize=1)
def _node_coords() -> dict[str, tuple[float, float]]:
    """Build a name→(lat,lon) dict from nodes.csv. Cached for the process lifetime."""
    try:
        import pandas as pd
        df = pd.read_csv(_NODES_CSV)
        name_col = "name" if "name" in df.columns else "city"
        return {str(row[name_col]): (float(row.lat), float(row.lon)) for _, row in df.iterrows()}
    except Exception:
        return {}


def _resolve_coords(node_name: str) -> tuple[float, float] | None:
    """Return (lat, lon) for any node name using a 3-tier lookup."""
    # 1. Exact match in nodes.csv
    nc = _node_coords()
    if node_name in nc:
        return nc[node_name]

    # 2. Exact match in CITY_COORDS (legacy city names)
    from config import CITY_COORDS
    if node_name in CITY_COORDS:
        return CITY_COORDS[node_name]

    # 3. Partial match — node names often embed a city (e.g. "Amazon FC Bangalore")
    for known_name, coords in nc.items():
        if known_name in node_name or node_name in known_name:
            return coords
    for city, coords in CITY_COORDS.items():
        if city in node_name:
            return coords

    return None


def _wmo_to_score(code: int) -> int:
    if code >= 95:
        return 2  # thunderstorm → Storm
    if code >= 51 or code in (45, 48):
        return 1  # rain / drizzle / fog → Rain
    return 0      # clear / partly cloudy → Sunny


def get_weather(node_name: str, timeout: int = 6) -> dict:
    """Return current weather for any node (warehouse / port / airport / city).

    Returns:
        score           int   0=Sunny  1=Rain  2=Storm
        label           str
        precipitation_mm float
        windspeed_kmh   float
        wmo_code        int
        resolved_name   str   which name was matched
        error           str | None
    """
    coords = _resolve_coords(node_name)
    if not coords:
        return {
            "score": 0, "label": "Sunny",
            "precipitation_mm": 0.0, "windspeed_kmh": 0.0,
            "wmo_code": 0, "resolved_name": node_name,
            "error": f"No coordinates found for '{node_name}'",
        }

    lat, lon = coords
    try:
        resp = requests.get(
            _BASE_URL,
            params={
                "latitude":  lat,
                "longitude": lon,
                "current":   "weathercode,precipitation,windspeed_10m",
                "timezone":  "Asia/Kolkata",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        cur   = resp.json()["current"]
        code  = int(cur.get("weathercode", 0))
        score = _wmo_to_score(code)
        labels = {0: "Sunny/Cloudy", 1: "Rain", 2: "Storm"}
        return {
            "score":            score,
            "label":            labels[score],
            "precipitation_mm": float(cur.get("precipitation", 0)),
            "windspeed_kmh":    float(cur.get("windspeed_10m", 0)),
            "wmo_code":         code,
            "resolved_name":    node_name,
            "error":            None,
        }
    except Exception as exc:
        return {
            "score": 0, "label": "Sunny",
            "precipitation_mm": 0.0, "windspeed_kmh": 0.0,
            "wmo_code": -1, "resolved_name": node_name,
            "error": str(exc),
        }


if __name__ == "__main__":
    test_nodes = [
        "Amazon FC Bhiwandi", "Flipkart FC Bangalore",
        "JNPT Port", "Mumbai Airport BOM",
        "Chennai Port", "Delhi Airport DEL",
    ]
    for node in test_nodes:
        w = get_weather(node)
        status = w["label"] if not w["error"] else f"ERROR: {w['error']}"
        print(f"{node:30s} -> {status:15s}  "
              f"rain={w['precipitation_mm']}mm  wind={w['windspeed_kmh']}km/h")
