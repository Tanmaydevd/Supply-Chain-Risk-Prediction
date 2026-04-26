"""Real-time traffic via TomTom Traffic Flow API with time-heuristic fallback.

Free tier: 2,500 requests/day.
Register at https://developer.tomtom.com/user/register and set the env var:
    set TOMTOM_API_KEY=<your_key>      # Windows CMD
    $env:TOMTOM_API_KEY="<your_key>"   # PowerShell

If no key is set, falls back to an IST time-of-day heuristic:
  08:00-10:00 and 17:00-20:00 -> High
  11:00-16:00                 -> Medium
  Night / early morning       -> Low
"""
from __future__ import annotations
import datetime
import requests

from config import TOMTOM_API_KEY
from services.weather_service import _resolve_coords  # reuse coord resolver

_FLOW_URL = (
    "https://api.tomtom.com/traffic/services/4"
    "/flowSegmentData/absolute/10/json"
)
_IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def _time_heuristic() -> tuple[int, str]:
    hour = datetime.datetime.now(_IST).hour
    if 8 <= hour <= 10 or 17 <= hour <= 20:
        return 2, "High"
    if 11 <= hour <= 16:
        return 1, "Medium"
    return 0, "Low"


def get_traffic(origin: str, destination: str | None = None, timeout: int = 6) -> dict:
    """Return current traffic condition for a route.

    Uses the origin city coordinate as the TomTom query point.
    `destination` is accepted for API symmetry but not used by TomTom
    (TomTom returns segment-level data, not point-to-point).

    Returns:
        {
            "score": int (0=Low, 1=Medium, 2=High),
            "label": str,
            "current_speed_kmh": float | None,
            "free_flow_speed_kmh": float | None,
            "congestion_ratio": float | None,   # 1.0 = free flow
            "source": "tomtom" | "time_heuristic",
            "error": str | None,
        }
    """
    if not TOMTOM_API_KEY:
        score, label = _time_heuristic()
        return {
            "score": score, "label": label,
            "current_speed_kmh": None, "free_flow_speed_kmh": None,
            "congestion_ratio": None,
            "source": "time_heuristic",
            "error": "TOMTOM_API_KEY not set — using time-of-day estimate",
        }

    coords = _resolve_coords(origin)
    if not coords:
        score, label = _time_heuristic()
        return {
            "score": score, "label": label,
            "current_speed_kmh": None, "free_flow_speed_kmh": None,
            "congestion_ratio": None,
            "source": "time_heuristic",
            "error": f"No coordinates found for '{origin}'",
        }

    lat, lon = coords
    try:
        resp = requests.get(
            _FLOW_URL,
            params={"point": f"{lat},{lon}", "key": TOMTOM_API_KEY},
            timeout=timeout,
        )
        resp.raise_for_status()
        seg = resp.json().get("flowSegmentData", {})
        current = float(seg.get("currentSpeed", 0))
        free_flow = float(seg.get("freeFlowSpeed", 1))
        ratio = current / max(free_flow, 1.0)

        if ratio < 0.40:
            score, label = 2, "High"
        elif ratio < 0.75:
            score, label = 1, "Medium"
        else:
            score, label = 0, "Low"

        return {
            "score": score, "label": label,
            "current_speed_kmh": round(current, 1),
            "free_flow_speed_kmh": round(free_flow, 1),
            "congestion_ratio": round(ratio, 2),
            "source": "tomtom",
            "error": None,
        }
    except Exception as exc:
        score, label = _time_heuristic()
        return {
            "score": score, "label": label,
            "current_speed_kmh": None, "free_flow_speed_kmh": None,
            "congestion_ratio": None,
            "source": "time_heuristic",
            "error": str(exc),
        }


if __name__ == "__main__":
    pairs = [("Mumbai", "Pune"), ("Delhi", "Jaipur"), ("Bangalore", "Chennai")]
    for orig, dest in pairs:
        t = get_traffic(orig, dest)
        print(f"{orig}->{dest}: {t['label']} (score={t['score']}, "
              f"source={t['source']})")
        if t["error"]:
            print(f"  note: {t['error']}")
