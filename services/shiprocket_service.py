"""Shiprocket real-time Indian e-commerce shipping service.

Shiprocket is India's #1 e-commerce shipping platform used by 1 lakh+
sellers on Flipkart, Amazon, Meesho, Shopify stores.

It provides REAL order + shipment data from Indian sellers.

FREE ACCOUNT SETUP:
  1. Register at https://app.shiprocket.in/register (free)
  2. Use your email/password below or set env vars:
       set SHIPROCKET_EMAIL=your@email.com
       set SHIPROCKET_PASSWORD=yourpassword

  The API issues a JWT token valid for 10 days.

API Docs: https://apidocs.shiprocket.in/
"""
from __future__ import annotations
import os
import requests
import datetime

SHIPROCKET_EMAIL    = os.environ.get("SHIPROCKET_EMAIL", "")
SHIPROCKET_PASSWORD = os.environ.get("SHIPROCKET_PASSWORD", "")
_BASE    = "https://apiv2.shiprocket.in/v1/external"
_token   = None
_token_ts: datetime.datetime | None = None


def _get_token() -> str | None:
    global _token, _token_ts
    if not SHIPROCKET_EMAIL or not SHIPROCKET_PASSWORD:
        return None
    # reuse token for 9 days
    if _token and _token_ts and (datetime.datetime.utcnow() - _token_ts).days < 9:
        return _token
    try:
        resp = requests.post(
            f"{_BASE}/auth/login",
            json={"email": SHIPROCKET_EMAIL, "password": SHIPROCKET_PASSWORD},
            timeout=8,
        )
        resp.raise_for_status()
        _token    = resp.json()["token"]
        _token_ts = datetime.datetime.utcnow()
        return _token
    except Exception as exc:
        print(f"[shiprocket] login failed: {exc}")
        return None


def _headers() -> dict:
    token = _get_token()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_orders(per_page: int = 20) -> list[dict]:
    """Fetch recent orders from your Shiprocket account.

    Returns normalised shipment dicts compatible with our /api/shipments schema.
    """
    h = _headers()
    if not h:
        return _demo_orders()
    try:
        resp = requests.get(
            f"{_BASE}/orders",
            headers=h,
            params={"per_page": per_page, "sort": "created_at", "sort_order": "DESC"},
            timeout=10,
        )
        resp.raise_for_status()
        return [_normalise_order(o) for o in resp.json().get("data", {}).get("data", [])]
    except Exception as exc:
        print(f"[shiprocket] orders fetch failed ({exc}) — demo data")
        return _demo_orders()


def track_shipment(shipment_id: str) -> dict:
    """Get real-time tracking for a specific Shiprocket shipment."""
    h = _headers()
    if not h:
        return {"error": "SHIPROCKET_EMAIL / PASSWORD not set"}
    resp = requests.get(f"{_BASE}/courier/track/shipment/{shipment_id}",
                        headers=h, timeout=8)
    return resp.json()


def get_ndr_shipments() -> list[dict]:
    """Non-Delivery Report — orders that failed first delivery attempt.

    These are the highest-risk shipments and map directly to our delay model.
    """
    h = _headers()
    if not h:
        return []
    try:
        resp = requests.get(f"{_BASE}/ndr/all", headers=h,
                            params={"per_page": 20}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as exc:
        print(f"[shiprocket] NDR fetch failed: {exc}")
        return []


# Risk mapping from Shiprocket order statuses
_SR_STATUS_RISK = {
    "DELIVERED":              0.0,
    "IN TRANSIT":             0.25,
    "OUT FOR DELIVERY":       0.20,
    "UNDELIVERED":            0.75,
    "RTO INITIATED":          0.85,
    "RTO DELIVERED":          0.90,
    "PENDING":                0.40,
    "PICKUP SCHEDULED":       0.30,
    "PICKUP ERROR":           0.70,
    "LOST":                   0.95,
    "DAMAGED":                0.90,
}

INDIAN_CITY_MAP = {
    "maharashtra": "Mumbai", "delhi": "Delhi", "karnataka": "Bangalore",
    "tamil nadu": "Chennai", "west bengal": "Kolkata", "gujarat": "Ahmedabad",
    "rajasthan": "Jaipur", "uttar pradesh": "Lucknow", "telangana": "Hyderabad",
    "andhra pradesh": "Visakhapatnam", "madhya pradesh": "Bhopal",
    "maharashtra-pune": "Pune",
}


def _normalise_order(o: dict) -> dict:
    status = str(o.get("status", "IN TRANSIT")).upper()
    risk   = _SR_STATUS_RISK.get(status, 0.40)
    state  = str(o.get("pickup_address", {}).get("state", "maharashtra")).lower()
    dest_state = str(o.get("delivery_address", {}).get("state", "delhi")).lower()
    return {
        "id":          str(o.get("id", "N/A")),
        "carrier":     o.get("courier_name", "Shiprocket"),
        "status":      status.title(),
        "risk":        risk,
        "source":      INDIAN_CITY_MAP.get(state, "Mumbai") + ", IN",
        "destination": INDIAN_CITY_MAP.get(dest_state, "Delhi") + ", IN",
        "eta":         str(o.get("etd", "")),
        "title":       o.get("channel_name", "E-Commerce Order"),
        "weight_kg":   o.get("total_weight", 1.0),
        "last_updated": o.get("updated_at", ""),
        "data_source": "Shiprocket Live",
    }


def _demo_orders() -> list[dict]:
    import random
    today = datetime.date.today()
    cities = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad",
              "Kolkata", "Pune", "Ahmedabad"]
    statuses = [("In Transit", 0.25), ("Delayed", 0.60),
                ("Out For Delivery", 0.20), ("Undelivered", 0.75)]
    rows = []
    for i in range(8):
        st, risk = statuses[i % len(statuses)]
        src = cities[i % len(cities)]
        dst = cities[(i + 3) % len(cities)]
        rows.append({
            "id":          f"SR-{10001 + i}",
            "carrier":     ["Delhivery", "Ekart", "Xpressbees"][i % 3],
            "status":      st,
            "risk":        risk,
            "source":      f"{src}, IN",
            "destination": f"{dst}, IN",
            "eta":         (today + datetime.timedelta(days=i+1)).isoformat(),
            "title":       f"Order #{10001+i}",
            "weight_kg":   round(0.5 + i * 0.8, 1),
            "last_updated": datetime.datetime.utcnow().isoformat(),
            "data_source": "Demo (set SHIPROCKET_EMAIL + PASSWORD for live data)",
        })
    return rows
