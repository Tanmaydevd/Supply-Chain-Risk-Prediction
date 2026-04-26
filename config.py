"""Central configuration: paths, thresholds, encodings."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Auto-load .env file if it exists (keeps API keys out of source code)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "trained_models"

# Categorical encodings (keep consistent across preprocess + UI)
WEATHER_MAP = {"Sunny": 0, "Cloudy": 0, "Rain": 1, "Storm": 2}
TRAFFIC_MAP = {"Low": 0, "Medium": 1, "High": 2}

# Risk thresholds (probability buckets)
RISK_THRESHOLDS = {"low": 0.33, "medium": 0.66}  # >= 0.66 -> High

# Synthetic data generation
N_SYNTHETIC_SHIPMENTS = 5000
RANDOM_SEED = 42

# City lat/lon — used by weather + traffic APIs
# Includes all node names from nodes.csv so API lookups work for every hub/port/airport
CITY_COORDS: dict[str, tuple[float, float]] = {
    # ── Legacy plain-city names (kept for backward compat) ───────────────────
    "Bangalore":     (12.9716,  77.5946),
    "Chennai":       (13.0827,  80.2707),
    "Hyderabad":     (17.3850,  78.4867),
    "Mumbai":        (19.0760,  72.8777),
    "Delhi":         (28.7041,  77.1025),
    "Kolkata":       (22.5726,  88.3639),
    "Pune":          (18.5204,  73.8567),
    "Ahmedabad":     (23.0225,  72.5714),
    "Jaipur":        (26.9124,  75.7873),
    "Lucknow":       (26.8467,  80.9462),
    "Coimbatore":    (11.0168,  76.9558),
    "Kochi":         (9.9312,   76.2673),
    "Nagpur":        (21.1458,  79.0882),
    "Bhopal":        (23.2599,  77.4126),
    "Visakhapatnam": (17.6868,  83.2185),

    # ── Fulfillment Centres & 3PL Hubs ───────────────────────────────────────
    "Amazon FC Bhiwandi":        (19.2967, 73.0593),
    "Flipkart FC Bhiwandi":      (19.3100, 73.0650),
    "Amazon FC Manesar":         (28.3500, 76.9300),
    "Delhivery Hub Gurgaon":     (28.4595, 77.0266),
    "Amazon FC Noida":           (28.5355, 77.3910),
    "Flipkart FC Bangalore":     (12.8389, 77.6627),
    "Amazon FC Bangalore":       (12.9120, 77.6500),
    "Amazon FC Hyderabad":       (17.4126, 78.4072),
    "Amazon FC Chennai":         (12.9824, 80.2181),
    "Amazon FC Kolkata":         (22.6328, 88.3793),
    "XpressBees Hub Pune":       (18.6526, 73.8524),
    "Delhivery Hub Jaipur":      (26.8935, 75.7568),
    "Ecom Express Lucknow":      (26.8701, 80.9462),
    "Blue Dart Hub Ahmedabad":   (23.0653, 72.5897),
    "Amazon FC Surat":           (21.1702, 72.8311),
    "Mahindra Logistics Nagpur": (21.0762, 79.0415),
    "Delhivery Hub Coimbatore":  (11.0168, 76.9558),
    "Amazon FC Kochi":           (10.0227, 76.3267),
    "Amazon FC Visakhapatnam":   (17.7231, 83.3012),
    "Ludhiana Industrial Hub":   (30.9010, 75.8573),
    "Panipat Textile Hub":       (29.3909, 76.9635),
    "Tiruppur Textile Hub":      (11.1085, 77.3411),
    "Rajkot Industrial Hub":     (22.3039, 70.8022),
    "Blue Dart Hub Indore":      (22.7196, 75.8577),
    "Delhivery Hub Patna":       (25.5941, 85.1376),
    "WCI Bhubaneswar":           (20.2961, 85.8245),
    "Amazon FC Chandigarh":      (30.7333, 76.7794),
    "Flipkart Hub Vadodara":     (22.3072, 73.1812),

    # ── Seaports ─────────────────────────────────────────────────────────────
    "JNPT Port":            (18.9500, 72.9333),
    "Mumbai Port":          (18.9220, 72.8347),
    "Kandla Port":          (22.9500, 70.2000),
    "Mundra Port":          (22.8395, 69.7060),
    "Chennai Port":         (13.0900, 80.2900),
    "Ennore Port":          (13.2167, 80.3167),
    "Visakhapatnam Port":   (17.6932, 83.2771),
    "Paradip Port":         (20.3167, 86.6167),
    "Kolkata Port":         (22.5800, 88.3200),
    "Haldia Port":          (22.0621, 88.0684),
    "Kochi Port":           (9.9667,  76.2667),
    "New Mangalore Port":   (12.9201, 74.8100),
    "Mormugao Port":        (15.4000, 73.8000),
    "Tuticorin Port":       (8.7642,  78.1348),

    # ── Cargo Airports ───────────────────────────────────────────────────────
    "Mumbai Airport BOM":    (19.0896, 72.8656),
    "Delhi Airport DEL":     (28.5665, 77.1031),
    "Bangalore Airport BLR": (13.1986, 77.7066),
    "Chennai Airport MAA":   (12.9941, 80.1709),
    "Kolkata Airport CCU":   (22.6520, 88.4463),
    "Hyderabad Airport HYD": (17.2403, 78.4294),
    "Ahmedabad Airport AMD": (23.0772, 72.6347),
    "Kochi Airport COK":     (10.1520, 76.4019),
    "Pune Airport PNQ":      (18.5822, 73.9197),
    "Nagpur Airport NAG":    (21.0922, 79.0472),
}

# TomTom Traffic Flow API key (free tier)
# Register at https://developer.tomtom.com/user/register
# Set via environment variable or paste directly (not committed to git)
TOMTOM_API_KEY: str = os.environ.get("TOMTOM_API_KEY", "")
