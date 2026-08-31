"""
Real, free-tier keyword/rank data — replaces the old `sum(ord(c) for c in
keyword)` checksum trick that faked SERP positions and search volume.

Two free sources:

1. SerpApi (https://serpapi.com/) — 250 free searches/month, recurring
   (not a one-time trial), no billing required for the free tier. Used
   here to find a domain's real position in the top-10 organic results
   for a keyword. Needs SERPAPI_KEY.
   (Previously used Google Custom Search JSON API for this, but Google
   discontinued free whole-web search for any Programmable Search Engine
   created after Jan 23, 2026 — new engines are permanently capped at
   site-restricted search, which broke real whole-web rank checks.)

2. Google Trends via pytrends (unofficial, no key needed, fully free) —
   used as a relative search-interest proxy since real historical search
   *volume* is not available from any free API.

Both are best-effort: if not configured, or if the (rate-limited/unofficial)
Trends endpoint is blocked, functions return None so callers fall back to
clearly-labeled simulated data instead of crashing.
"""
import os
import httpx

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")


def is_serp_configured() -> bool:
    return bool(SERPAPI_KEY)


def check_real_rank(keyword: str, domain: str):
    """Real top-10 SERP check via SerpApi's Google Search API (free tier)."""
    if not is_serp_configured():
        return None
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://serpapi.com/search",
                params={"engine": "google", "api_key": SERPAPI_KEY, "q": keyword, "num": 10},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("organic_results", [])
            position = None
            for item in items:
                if domain.lower() in item.get("link", "").lower():
                    position = item.get("position")
                    break
            return {
                "position": position,  # None = not found in the top 10 checked
                "checked_top_n": len(items),
                "total_results_reported": data.get("search_information", {}).get("total_results"),
                "source": "serpapi_google_search",
            }
    except Exception as e:
        print(f"[serp] SerpApi lookup failed: {e}")
        return None


def get_trend_interest(keyword: str):
    """Relative search-interest proxy (0-100) via Google Trends (free, unofficial)."""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=0, timeout=(5, 10))
        pytrends.build_payload([keyword], timeframe="today 3-m")
        df = pytrends.interest_over_time()
        if df is None or df.empty or keyword not in df.columns:
            return None
        return {
            "average_interest_0_100": round(float(df[keyword].mean()), 1),
            "latest_interest_0_100": int(df[keyword].iloc[-1]),
            "source": "google_trends",
        }
    except Exception as e:
        print(f"[serp] Google Trends lookup failed (this is common on datacenter IPs / rate limits): {e}")
        return None
