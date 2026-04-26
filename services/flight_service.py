"""Real-time cargo flight tracking via OpenSky Network.

100% FREE — no API key, no registration required.
Docs: https://opensky-network.org/apidoc/rest.html

Returns all aircraft currently flying over India's bounding box.
Filters for known cargo airline callsign prefixes.

India bounding box: lat 8–37 N, lon 68–97 E
"""
from __future__ import annotations
import requests
import datetime

_OPENSKY = "https://opensky-network.org/api/states/all"

# India bounding box
_INDIA = {"lamin": 8.0, "lomin": 68.0, "lamax": 37.0, "lomax": 97.0}

# ICAO prefixes of cargo / freight airlines operating India routes
_CARGO_PREFIXES = {
    "FDX",   # FedEx
    "UPS",   # UPS Airlines
    "CLX",   # Cargolux
    "TAY",   # TNT Airways
    "MSR",   # EgyptAir Cargo
    "SIA",   # Singapore Air Cargo
    "CPA",   # Cathay Pacific Cargo
    "IAW",   # Iraqi Airways Cargo
    "QTR",   # Qatar Airways Cargo
    "ETH",   # Ethiopian Cargo
    "UAE",   # Emirates SkyCargo
    "THA",   # Thai Cargo
    "AAR",   # Asiana Cargo
    "KAL",   # Korean Air Cargo
    "AIC",   # Air India Cargo
    "BLF",   # Blue Dart Aviation
    "DAL",   # DHL Air (Delta prefix)
    "DHX",   # DHL Express
    "TGW",   # TG/Thai Cargo
    "LDA",   # Lufthansa Cargo
    "ABX",   # ABX Air
    "GTI",   # Atlas Air
    "NPT",   # Air India Express
    "IGO",   # IndiGo (passenger but carries belly cargo)
    "AXB",   # Air Arabia (cargo)
    "FDB",   # flydubai (carries cargo)
}

# Indian cargo airports (IATA codes, for display)
INDIAN_CARGO_AIRPORTS = {
    "BOM": ("Mumbai",     19.0896, 72.8656),
    "DEL": ("Delhi",      28.5665, 77.1031),
    "BLR": ("Bangalore",  13.1986, 77.7066),
    "MAA": ("Chennai",    12.9941, 80.1709),
    "CCU": ("Kolkata",    22.6520, 88.4463),
    "HYD": ("Hyderabad",  17.2403, 78.4294),
    "AMD": ("Ahmedabad",  23.0772, 72.6347),
    "COK": ("Kochi",      10.1520, 76.4019),
    "PNQ": ("Pune",       18.5822, 73.9197),
    "NAG": ("Nagpur",     21.0922, 79.0472),
}


def get_cargo_flights(timeout: int = 8) -> list[dict]:
    """Return real-time cargo flights over India from OpenSky Network.

    Each dict:
        callsign, lat, lon, altitude_m, velocity_kmh, heading,
        on_ground, icao24, is_cargo, origin_country
    """
    try:
        resp = requests.get(_OPENSKY, params=_INDIA, timeout=timeout)
        resp.raise_for_status()
        states = resp.json().get("states") or []
    except Exception as exc:
        print(f"[flight] OpenSky fetch failed ({exc}) — using demo data")
        return _demo_flights()

    flights = []
    for s in states:
        if not s or len(s) < 11:
            continue
        icao24        = s[0] or ""
        callsign      = (s[1] or "").strip()
        origin_ctry   = s[2] or "Unknown"
        lon           = s[5]
        lat           = s[6]
        altitude_m    = s[7] or 0
        on_ground     = bool(s[8])
        velocity_ms   = s[9] or 0
        heading       = s[10] or 0

        if lat is None or lon is None:
            continue

        prefix = callsign[:3].upper() if len(callsign) >= 3 else ""
        is_cargo = prefix in _CARGO_PREFIXES

        flights.append({
            "icao24":         icao24,
            "callsign":       callsign or "N/A",
            "origin_country": origin_ctry,
            "lat":            round(lat, 4),
            "lon":            round(lon, 4),
            "altitude_m":     round(altitude_m, 0) if altitude_m else 0,
            "velocity_kmh":   round(velocity_ms * 3.6, 1) if velocity_ms else 0,
            "heading":        round(heading, 0) if heading else 0,
            "on_ground":      on_ground,
            "is_cargo":       is_cargo,
        })

    # sort: cargo first, then by altitude
    flights.sort(key=lambda f: (not f["is_cargo"], -f["altitude_m"]))
    return flights


def get_cargo_only(timeout: int = 8) -> list[dict]:
    """Only known cargo carrier flights."""
    return [f for f in get_cargo_flights(timeout) if f["is_cargo"]]


def get_flight_delay_risk(callsign: str, flights: list[dict] | None = None) -> dict:
    """Estimate delay risk for a specific flight.

    Factors:
    - Altitude (low = approach, high = cruise — lower risk)
    - Velocity (low = slow, potential delay)
    - On ground (check-in / loading delay)
    """
    if flights is None:
        flights = get_cargo_flights()
    match = next((f for f in flights if f["callsign"] == callsign), None)
    if not match:
        return {"risk": 0.3, "status": "Unknown", "detail": "Not tracked"}

    if match["on_ground"]:
        risk, status = 0.6, "Ground — Loading/Unloading"
    elif match["altitude_m"] < 1500:
        risk, status = 0.5, "Approach/Departure — High turbulence zone"
    elif match["velocity_kmh"] < 400:
        risk, status = 0.45, "Slow cruise — possible holding pattern"
    else:
        risk, status = 0.2, "En route — normal"

    return {
        "callsign": callsign,
        "risk":     round(risk, 2),
        "status":   status,
        "altitude_m":   match["altitude_m"],
        "velocity_kmh": match["velocity_kmh"],
    }


def _demo_flights() -> list[dict]:
    """Realistic demo flights used when OpenSky is unreachable."""
    import math, random
    random.seed(int(datetime.datetime.utcnow().timestamp() / 300))  # changes every 5 min
    demos = [
        ("AIC101",  "AIC", 19.09,  72.87,  11000, 820,  270, False, "India"),
        ("FDX5071", "FDX", 22.65,  88.35,   9500, 780,  90,  False, "United States"),
        ("UAE512",  "UAE", 28.57,  77.10,  10500, 900,  315, False, "United Arab Emirates"),
        ("BLF101",  "BLF", 12.94,  80.17,   5000, 420,  180, False, "India"),
        ("DHX243",  "DHX", 17.24,  78.43,   8000, 750,  45,  False, "Germany"),
        ("GTI7402", "GTI", 13.20,  77.71,  11500, 850,  270, False, "United States"),
        ("QTR8211", "QTR", 9.95,   76.40,   9000, 880,  320, False, "Qatar"),
        ("ETH707",  "ETH", 20.30,  86.62,  10000, 820,  100, False, "Ethiopia"),
    ]
    return [
        {
            "icao24": f"demo{i:04d}", "callsign": cs, "origin_country": oc,
            "lat": lat + random.uniform(-0.5,0.5),
            "lon": lon + random.uniform(-0.5,0.5),
            "altitude_m": alt, "velocity_kmh": vel,
            "heading": hdg, "on_ground": gnd,
            "is_cargo": pfx in _CARGO_PREFIXES,
        }
        for i,(cs,pfx,lat,lon,alt,vel,hdg,gnd,oc) in enumerate(demos)
    ]


if __name__ == "__main__":
    print("Fetching live flights over India (OpenSky)...")
    flights = get_cargo_flights()
    cargo   = [f for f in flights if f["is_cargo"]]
    print(f"Total aircraft: {len(flights)}  |  Cargo carriers: {len(cargo)}")
    for f in cargo[:10]:
        print(f"  {f['callsign']:10s}  lat={f['lat']}  lon={f['lon']}"
              f"  alt={f['altitude_m']}m  spd={f['velocity_kmh']}km/h"
              f"  {'ON GROUND' if f['on_ground'] else 'AIRBORNE'}")
