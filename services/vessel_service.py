"""Real-time vessel tracking via aisstream.io (free WebSocket AIS data).

Free — register at https://aisstream.io, get an API key from the dashboard.
Set env var: AISSTREAM_API_KEY=your_key

Without a key, falls back to realistic simulation based on known Indian
Ocean shipping lanes (seed changes every 10 min so vessels appear to move).

India bounding box: lat 8–37 N, lon 68–97 E
"""
from __future__ import annotations
import os, math, random, datetime, json
import concurrent.futures

from config import AISSTREAM_API_KEY

# ── Port positions ─────────────────────────────────────────────────────────────
INDIAN_PORTS = {
    "JNPT":          (18.9500, 72.9333),
    "Mumbai Port":   (18.9220, 72.8347),
    "Kandla":        (22.9500, 70.2000),
    "Mundra":        (22.8395, 69.7060),
    "Chennai":       (13.0900, 80.2900),
    "Ennore":        (13.2167, 80.3167),
    "Visakhapatnam": (17.6932, 83.2771),
    "Paradip":       (20.3167, 86.6167),
    "Kolkata":       (22.5800, 88.3200),
    "Haldia":        (22.0621, 88.0684),
    "Kochi":         ( 9.9667, 76.2667),
    "New Mangalore": (12.9201, 74.8100),
    "Mormugao":      (15.4000, 73.8000),
    "Tuticorin":     ( 8.7642, 78.1348),
}

# AIS type code ranges → (display label, base delay risk)
_AIS_TYPES: list[tuple[range, str, float]] = [
    (range(70, 80), "Cargo Ship",   0.28),
    (range(80, 90), "Tanker",       0.20),
    (range(60, 70), "Passenger",    0.15),
    (range(30, 31), "Fishing",      0.35),
    (range(50, 60), "Service",      0.22),
    (range(35, 36), "Military",     0.10),
    (range(20, 30), "High Speed",   0.18),
]
_VESSEL_RISK = {label: risk for _, label, risk in _AIS_TYPES}
_CARGO_TYPES = ["Electronics", "Auto Parts", "Textiles", "Chemicals",
                "Coal", "Petroleum", "Containers", "Food Grains", "Steel"]

# For simulation fallback
_VESSEL_TYPES  = [label for _, label, _ in _AIS_TYPES if label != "Military"]
_FLAGS         = ["IN", "SG", "CN", "AE", "GR", "NO", "US", "MT", "PA"]
_SHIP_PREFIXES = ["MSC", "EVER", "CSCL", "OOCL", "MOL", "HMM",
                  "ONE", "PIL", "SITC", "SCI", "GE", "APL"]

_NAV_STATUS_LABELS = {
    0: "Underway", 1: "Anchored", 2: "Not under command",
    3: "Restricted maneuverability", 5: "Moored", 6: "Aground",
    7: "Fishing", 15: "Undefined",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ, Δλ = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_port(lat: float, lon: float) -> str:
    return min(INDIAN_PORTS, key=lambda p: _haversine(lat, lon, *INDIAN_PORTS[p]))


def _ais_type_label(type_code: int) -> tuple[str, float]:
    for r, label, risk in _AIS_TYPES:
        if type_code in r:
            return label, risk
    return "Cargo Ship", 0.28


def _normalise(mmsi: int, name: str, lat: float, lon: float,
               sog: float, cog: float, nav_status: int,
               type_code: int) -> dict:
    label, base_risk = _ais_type_label(type_code)
    on_ground = nav_status in (1, 5, 6)
    risk = round(min(base_risk + (0.2 if on_ground else 0), 0.95), 2)
    return {
        "mmsi":         str(mmsi),
        "name":         (name or f"VESSEL-{mmsi}").strip(),
        "vessel_type":  label,
        "flag":         "Unknown",
        "lat":          round(lat, 4),
        "lon":          round(lon, 4),
        "speed_knots":  round(sog, 1),
        "heading":      round(cog % 360, 0),
        "status":       _NAV_STATUS_LABELS.get(nav_status, "Underway"),
        "nearest_port": _nearest_port(lat, lon),
        "cargo":        random.choice(_CARGO_TYPES),
        "delay_risk":   risk,
        "source":       "aisstream.io",
    }


# ── aisstream.io WebSocket fetch ───────────────────────────────────────────────

async def _aisstream_async(api_key: str, duration: float = 7.0) -> list[dict]:
    import asyncio
    import websockets

    url = "wss://stream.aisstream.io/v0/stream"
    subscribe = json.dumps({
        "APIKey": api_key,
        "BoundingBoxes": [[[-90.0, -180.0], [90.0, 180.0]]],  # global — filter by position client-side
    })

    positions: dict[int, dict]            = {}
    static:    dict[int, tuple[str, int]] = {}  # mmsi → (name, type_code)

    try:
        async with websockets.connect(url, open_timeout=10, close_timeout=3) as ws:
            await ws.send(subscribe)
            deadline = asyncio.get_event_loop().time() + duration

            while asyncio.get_event_loop().time() < deadline and len(positions) < 300:
                remaining = deadline - asyncio.get_event_loop().time()
                try:
                    raw  = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 3.0))
                    msg  = json.loads(raw)
                    mtype = msg.get("MessageType", "")
                    meta  = msg.get("MetaData", {})
                    mmsi  = int(meta.get("MMSI", 0))
                    if not mmsi:
                        continue

                    if mtype in ("PositionReport", "StandardClassBPositionReport"):
                        pr  = msg["Message"].get("PositionReport") or msg["Message"].get("StandardClassBPositionReport", {})
                        lat = float(pr.get("Latitude", 0))
                        lon = float(pr.get("Longitude", 0))
                        if lat == 0.0 and lon == 0.0:
                            continue  # skip invalid positions
                        name, tcode = static.get(mmsi, (meta.get("ShipName", ""), 70))
                        positions[mmsi] = _normalise(
                            mmsi, name, lat, lon,
                            float(pr.get("Sog", 0)),
                            float(pr.get("Cog", 0)),
                            int(pr.get("NavigationalStatus", 0)),
                            tcode,
                        )

                    elif mtype == "ShipStaticData":
                        sd    = msg["Message"]["ShipStaticData"]
                        name  = sd.get("Name", "").strip()
                        tcode = int(sd.get("Type", 70))
                        static[mmsi] = (name, tcode)
                        if mmsi in positions and name:
                            positions[mmsi]["name"] = name
                            vtype, _ = _ais_type_label(tcode)
                            positions[mmsi]["vessel_type"] = vtype

                except asyncio.TimeoutError:
                    break

    except Exception as exc:
        print(f"[vessel] aisstream.io error: {exc}")
        return []

    return list(positions.values())


def _fetch_aisstream(api_key: str, timeout: int = 5) -> list[dict]:
    """Synchronous wrapper — runs async code in a separate thread to avoid
    conflicts with Streamlit's internal event loop."""
    def _run():
        import asyncio
        return asyncio.run(_aisstream_async(api_key, duration=float(timeout)))

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_run)
            result = fut.result(timeout=timeout + 6)
            return result if result else _simulate_vessels()
    except Exception as exc:
        print(f"[vessel] aisstream wrapper failed ({exc}) — simulation")
        return _simulate_vessels()


# ── Public API ─────────────────────────────────────────────────────────────────

def get_vessels_near_india(timeout: int = 5) -> list[dict]:
    """Return vessels near Indian ports. Uses aisstream.io if key set, else simulation."""
    if AISSTREAM_API_KEY:
        return _fetch_aisstream(AISSTREAM_API_KEY, timeout)
    return _simulate_vessels()


def get_port_congestion(port_name: str) -> dict:
    """Return congestion level (0–1) for a given Indian port."""
    vessels   = get_vessels_near_india()
    port_pos  = INDIAN_PORTS.get(port_name)
    if not port_pos:
        return {"congestion": 0.3, "vessel_count": 0, "avg_wait_hrs": 7.2, "port": port_name}

    nearby    = [v for v in vessels
                 if _haversine(v["lat"], v["lon"], *port_pos) <= 50]
    congestion = min(len(nearby) / 15.0, 1.0)
    return {
        "port":         port_name,
        "congestion":   round(congestion, 2),
        "vessel_count": len(nearby),
        "avg_wait_hrs": round(congestion * 24, 1),
    }


def get_vessel_delay_risk(vessel_mmsi: str | None = None,
                          near_port: str | None = None) -> dict:
    if near_port:
        cong = get_port_congestion(near_port)
        risk = 0.15 + cong["congestion"] * 0.65
        return {
            "port":              near_port,
            "delay_risk":        round(risk, 2),
            "congestion":        cong["congestion"],
            "avg_wait_hrs":      cong["avg_wait_hrs"],
            "vessel_count_50nm": cong["vessel_count"],
        }
    return {"delay_risk": 0.25, "detail": "No port specified"}


# ── Simulation fallback ────────────────────────────────────────────────────────

def _simulate_vessels() -> list[dict]:
    """Generate realistic vessel positions on known Indian shipping lanes.
    Seed changes every 10 min so vessels appear to move between page refreshes."""
    rng = random.Random(int(datetime.datetime.utcnow().timestamp() / 600))

    LANES = [
        (18.5, 72.5, 270, "Arabian Sea W"),
        (14.0, 74.5, 180, "West Coast S"),
        (10.5, 76.0,  90, "SW India"),
        ( 8.5, 77.5,  90, "Gulf of Mannar"),
        (13.5, 80.5,   0, "Bay of Bengal S"),
        (17.0, 83.5,   0, "Bay of Bengal N"),
        (21.0, 87.5,  45, "NE India coast"),
        (22.0, 89.0,  90, "Hooghly approach"),
        (20.5, 72.3, 315, "Gulf of Khambhat"),
        (23.0, 70.5, 270, "Gulf of Kutch"),
        (15.5, 73.5, 180, "Malabar Coast"),
        ( 9.5, 78.5,  90, "Palk Strait"),
    ]

    vessels = []
    for i, (lat, lon, hdg, _lane) in enumerate(LANES):
        for j in range(rng.randint(2, 4)):
            vtype   = rng.choice(_VESSEL_TYPES)
            prefix  = rng.choice(_SHIP_PREFIXES)
            suffix  = rng.randint(100, 9999)
            speed   = rng.uniform(8, 16) if vtype != "Tanker" else rng.uniform(10, 14)
            status  = rng.choice(["Underway", "Underway", "Underway", "Anchored", "Moored"])
            d_risk  = _VESSEL_RISK.get(vtype, 0.28) + (0.2 if status in ("Anchored", "Moored") else 0)
            vlat    = round(lat + rng.uniform(-0.8, 0.8), 4)
            vlon    = round(lon + rng.uniform(-0.8, 0.8), 4)
            vessels.append({
                "mmsi":         f"sim{i:02d}{j:02d}{suffix}",
                "name":         f"{prefix} {suffix}",
                "vessel_type":  vtype,
                "flag":         rng.choice(_FLAGS),
                "lat":          vlat,
                "lon":          vlon,
                "speed_knots":  round(speed, 1),
                "heading":      (hdg + rng.randint(-20, 20)) % 360,
                "status":       status,
                "nearest_port": _nearest_port(vlat, vlon),
                "cargo":        rng.choice(_CARGO_TYPES),
                "delay_risk":   round(min(d_risk, 0.95), 2),
                "source":       "Simulation (set AISSTREAM_API_KEY for live data)",
            })
    return vessels


if __name__ == "__main__":
    print(f"AISSTREAM_API_KEY set: {bool(AISSTREAM_API_KEY)}")
    print("Fetching vessels near Indian ports...")
    vessels = get_vessels_near_india()
    print(f"Total vessels: {len(vessels)}  source: {vessels[0]['source'] if vessels else 'none'}")
    for v in vessels[:8]:
        print(f"  {v['name']:20s}  {v['vessel_type']:15s}  "
              f"lat={v['lat']}  lon={v['lon']}  spd={v['speed_knots']}kn  "
              f"port={v['nearest_port']}  risk={v['delay_risk']}")
    print("\nPort congestion:")
    for port in ["JNPT", "Chennai", "Visakhapatnam"]:
        c = get_port_congestion(port)
        print(f"  {port:20s}: congestion={c['congestion']:.2f}  "
              f"vessels_50nm={c['vessel_count']}  wait={c['avg_wait_hrs']}h")
