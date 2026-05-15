"""AfterShip real shipment tracking service.

AfterShip supports 800+ carriers including all major Indian ones:
  Delhivery, DTDC, Blue Dart, Ekart (Flipkart), Xpressbees, Ecom Express,
  Amazon Logistics India, India Post, Shadowfax

FREE TIER: 100 trackings/month — enough for a demo/research project.

Setup (one-time):
  1. Register at https://www.aftership.com/signup (free)
  2. Go to Settings -> API Keys -> Create API Key
  3. Set environment variable:
       set AFTERSHIP_API_KEY=your_key_here        # Windows CMD
       $env:AFTERSHIP_API_KEY="your_key_here"     # PowerShell

API Docs: https://developers.aftership.com/reference/overview
"""
from __future__ import annotations
import os
import requests

try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

AFTERSHIP_KEY = os.environ.get("AFTERSHIP_API_KEY", "")
# asat_ keys use the newer AfterShip API (2024-07) with as-api-key header
_BASE    = "https://api.aftership.com/tracking/2024-07"
_HEADERS = {
    "as-api-key":   AFTERSHIP_KEY,
    "Content-Type": "application/json",
}

# Map AfterShip status tags to our risk model
_STATUS_TO_RISK = {
    "Delivered":         0.0,
    "InTransit":         0.25,
    "OutForDelivery":    0.20,
    "AttemptFail":       0.65,
    "Exception":         0.80,
    "Pending":           0.40,
    "InfoReceived":      0.30,
    "Failed":            0.90,
    "Expired":           0.95,
}


import json as _json
from pathlib import Path as _Path
import time as _time

_CACHE_FILE = _Path(__file__).resolve().parent.parent / "data" / "processed" / "aftership_cache.json"
_CACHE_TTL  = 600  # seconds


def _read_cache() -> list[dict] | None:
    try:
        if _CACHE_FILE.exists():
            blob = _json.loads(_CACHE_FILE.read_text())
            if _time.time() - blob.get("ts", 0) < _CACHE_TTL:
                return blob["data"]
    except Exception:
        pass
    return None


def _write_cache(data: list[dict]):
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(_json.dumps({"ts": _time.time(), "data": data}))
    except Exception:
        pass


def get_all_trackings(limit: int = 50) -> list[dict]:
    """Fetch all trackings — uses file cache to survive Streamlit restarts."""
    # 1. Return file cache if fresh (avoids hitting rate limit on restart)
    cached = _read_cache()
    if cached is not None:
        return cached

    if not AFTERSHIP_KEY:
        return []

    import time
    for attempt in range(3):
        try:
            resp = requests.get(
                f"{_BASE}/trackings",
                headers=_HEADERS,
                params={"limit": limit, "fields": "tracking_number,slug,tag,title,"
                        "origin_country_iso3,destination_country_iso3,"
                        "origin_city,origin_state,destination_city,destination_state,"
                        "estimated_delivery,last_updated_at,last_checkpoint"},
                timeout=8,
            )
            if resp.status_code == 429:
                time.sleep(2 ** attempt)  # backoff: 1s, 2s, 4s
                continue
            resp.raise_for_status()
            body = resp.json()
            raw    = (body.get("data") or {}).get("trackings") or body.get("trackings", [])
            result = [_normalise(t) for t in raw]
            _write_cache(result)  # persist so restarts don't burn quota
            return result
        except Exception as exc:
            print(f"[aftership] fetch failed ({exc})")
            return []
    return []


def add_tracking(tracking_number: str, slug: str, title: str = "") -> dict:
    """Add a new shipment to AfterShip tracking.

    slug examples: 'delhivery', 'dtdc', 'bluedart', 'ekart', 'xpressbees'
    """
    if not AFTERSHIP_KEY:
        return {"error": "AFTERSHIP_API_KEY not set"}
    payload = {"tracking": {"tracking_number": tracking_number, "slug": slug, "title": title}}
    resp = requests.post(f"{_BASE}/trackings", headers=_HEADERS, json=payload, timeout=8)
    return resp.json()


def get_tracking(slug: str, tracking_number: str) -> dict:
    """Get real-time status of a specific shipment."""
    if not AFTERSHIP_KEY:
        return {"error": "AFTERSHIP_API_KEY not set"}
    resp = requests.get(f"{_BASE}/trackings/{slug}/{tracking_number}",
                        headers=_HEADERS, timeout=8)
    resp.raise_for_status()
    return _normalise(resp.json()["data"]["tracking"])


def _normalise(t: dict) -> dict:
    tag  = t.get("tag", "InTransit")
    risk = _STATUS_TO_RISK.get(tag, 0.4)

    # Build city, state strings — fall back to country code if missing
    def _loc(city_key, state_key, country_key):
        city    = t.get(city_key, "") or ""
        state   = t.get(state_key, "") or ""
        country = t.get(country_key, "IND") or "IND"
        if city and state:   return f"{city}, {state}"
        if city:             return f"{city}, {country}"
        if state:            return f"{state}, {country}"
        return country

    # Last checkpoint — shows current location + event message
    cp      = t.get("last_checkpoint") or {}
    cp_loc  = cp.get("location") or cp.get("city") or ""
    cp_msg  = cp.get("message") or cp.get("tag_description") or ""
    cp_time = (cp.get("checkpoint_time") or "")[:16]

    # ETA formatting
    eta_raw = t.get("estimated_delivery") or ""
    eta     = eta_raw[:10] if eta_raw else "—"

    # Last updated formatting
    upd_raw = t.get("last_updated_at") or ""
    updated = upd_raw[:16].replace("T", " ") if upd_raw else "—"

    return {
        "id":           t.get("tracking_number", "N/A"),
        "carrier":      t.get("slug", "Unknown").upper(),
        "status":       tag,
        "risk":         risk,
        "source":       _loc("origin_city", "origin_state", "origin_country_iso3"),
        "destination":  _loc("destination_city", "destination_state", "destination_country_iso3"),
        "eta":          eta,
        "last_updated": updated,
        "checkpoint":   f"{cp_loc} — {cp_msg} ({cp_time})" if cp_loc else cp_msg,
        "title":        t.get("title", ""),
        "data_source":  "AfterShip Live",
    }


def _demo_trackings() -> list[dict]:
    """Demo data shown when no API key is set."""
    import datetime, random
    today = datetime.date.today()
    carriers = ["DELHIVERY", "DTDC", "BLUEDART", "EKART", "XPRESSBEES"]
    tags     = ["InTransit", "InTransit", "OutForDelivery", "AttemptFail", "Exception"]
    rows = []
    for i in range(8):
        tag  = tags[i % len(tags)]
        risk = _STATUS_TO_RISK[tag]
        rows.append({
            "id":          f"DL{8821000 + i}IN",
            "carrier":     carriers[i % len(carriers)],
            "status":      tag,
            "risk":        risk,
            "source":      "Mumbai, IN",
            "destination": ["Delhi", "Bangalore", "Chennai", "Kolkata"][i % 4] + ", IN",
            "eta":         (today + datetime.timedelta(days=i+1)).isoformat(),
            "title":       f"Shipment #{i+1}",
            "last_updated": datetime.datetime.utcnow().isoformat(),
            "data_source": "Demo (set AFTERSHIP_API_KEY for live data)",
        })
    return rows
