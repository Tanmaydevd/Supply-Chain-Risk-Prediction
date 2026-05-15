"""Real-time Indian logistics disruption news via GNews API.

Free tier: 100 requests/day, real-time articles.
Register at https://gnews.io to get an API key.

Set env var: GNEWS_API_KEY=your_key
"""
from __future__ import annotations
import os, requests, datetime

try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

GNEWS_KEY = os.environ.get("GNEWS_API_KEY", "")
_BASE     = "https://gnews.io/api/v4/search"

# Queries targeting Indian supply chain disruptions
_QUERIES = [
    "port strike OR logistics disruption OR cargo delay OR freight India",
]

_SEV_KEYWORDS = {
    "Critical": ["strike", "shutdown", "closure", "blockade", "flood", "cyclone", "storm"],
    "High":     ["delay", "disruption", "protest", "congestion", "accident", "fire"],
    "Medium":   ["slowdown", "traffic", "weather", "rain", "warning", "advisory"],
}

def _severity(title: str, desc: str) -> str:
    text = (title + " " + desc).lower()
    for sev, keywords in _SEV_KEYWORDS.items():
        if any(k in text for k in keywords):
            return sev
    return "Medium"

def _action(sev: str) -> str:
    return {"Critical": "Reroute advised", "High": "Monitor closely", "Medium": "Monitor"}[sev]

def _time_ago(published: str) -> str:
    try:
        dt  = datetime.datetime.fromisoformat(published.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        diff = now - dt
        if diff.seconds < 3600:   return f"{diff.seconds // 60}m ago"
        if diff.days == 0:        return f"{diff.seconds // 3600}h ago"
        return f"{diff.days}d ago"
    except Exception:
        return ""

def get_disruption_news(max_results: int = 5, timeout: int = 6) -> list[dict]:
    """Fetch real Indian logistics disruption news from GNews.

    Returns list of threat dicts compatible with Home.py threat feed format.
    """
    if not GNEWS_KEY:
        return []

    articles = []
    seen_titles = set()

    for query in _QUERIES:
        if len(articles) >= max_results:
            break
        try:
            resp = requests.get(
                _BASE,
                params={
                    "q":      query,
                    "lang":   "en",
                    "country":"in",
                    "max":    3,
                    "apikey": GNEWS_KEY,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            for a in resp.json().get("articles", []):
                title = a.get("title", "")
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                desc  = a.get("description", "") or ""
                sev   = _severity(title, desc)
                articles.append({
                    "title":   title[:60] + "..." if len(title) > 60 else title,
                    "loc":     a.get("source", {}).get("name", "India News"),
                    "sev":     sev,
                    "orders":  "—",
                    "action":  _action(sev),
                    "detail":  (desc[:80] + "...") if len(desc) > 80 else desc,
                    "time":    _time_ago(a.get("publishedAt", "")),
                    "url":     a.get("url", ""),
                })
                if len(articles) >= max_results:
                    break
        except Exception as exc:
            print(f"[news] GNews fetch failed for '{query}': {exc}")
            continue

    return articles


if __name__ == "__main__":
    news = get_disruption_news()
    print(f"Got {len(news)} disruption alerts:")
    for n in news:
        print(f"  [{n['sev']}] {n['title']} — {n['loc']} ({n['time']})")
