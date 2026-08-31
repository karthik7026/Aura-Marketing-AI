import os
import re
import datetime
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from pymongo.database import Database

from backend.database import get_db
from backend.deps import get_current_user as get_current_user_helper

router = APIRouter(prefix="/api", tags=["Web Audit & Competitor Scraper"])

PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "")


class LighthouseRequest(BaseModel):
    url: str
    strategy: Optional[str] = "mobile"


class CompetitorRequest(BaseModel):
    competitor_url: str


def _run_real_pagespeed_insights(target_url: str, strategy: str):
    """
    Google PageSpeed Insights API — genuinely free (a free API key raises
    the shared quota but isn't even required to try it), and it *is* real
    Lighthouse under the hood, unlike the old code here which hardcoded
    accessibility=88 and best_practices=90 for every single site.
    """
    try:
        params = {
            "url": target_url,
            "strategy": strategy or "mobile",
            "category": ["PERFORMANCE", "ACCESSIBILITY", "SEO", "BEST_PRACTICES"],
        }
        if PAGESPEED_API_KEY:
            params["key"] = PAGESPEED_API_KEY
        with httpx.Client(timeout=25.0) as client:
            resp = client.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed", params=params)
        if resp.status_code != 200:
            return None
        data = resp.json()
        lhr = data.get("lighthouseResult", {})
        cats = lhr.get("categories", {})
        audits = lhr.get("audits", {})

        def score_of(cat_key):
            v = cats.get(cat_key, {}).get("score")
            return round(v * 100) if v is not None else None

        return {
            "scores": {
                "performance": score_of("performance"),
                "seo": score_of("seo"),
                "accessibility": score_of("accessibility"),
                "best_practices": score_of("best-practices"),
            },
            "metrics": {
                "first_contentful_paint": audits.get("first-contentful-paint", {}).get("displayValue"),
                "largest_contentful_paint": audits.get("largest-contentful-paint", {}).get("displayValue"),
                "total_blocking_time": audits.get("total-blocking-time", {}).get("displayValue"),
                "cumulative_layout_shift": audits.get("cumulative-layout-shift", {}).get("displayValue"),
            },
        }
    except Exception as e:
        print(f"[webaudit] PageSpeed Insights call failed, falling back to heuristic: {e}")
        return None


@router.post("/webaudit/lighthouse")
def run_lighthouse_audit(
    req: LighthouseRequest,
    current_user: dict = Depends(get_current_user_helper),
):
    target_url = req.url.strip()
    if not target_url.startswith("http"):
        target_url = f"https://{target_url}"

    real = _run_real_pagespeed_insights(target_url, req.strategy or "mobile")
    if real:
        return {
            "status": "success",
            "url": target_url,
            "strategy": req.strategy,
            "data_source": "google_pagespeed_insights",
            **real,
        }

    # Fallback heuristic — now clearly labeled as an estimate, not real Lighthouse.
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36"}
    status_code = 200
    latency_ms = 320
    try:
        start = datetime.datetime.now()
        with httpx.Client(timeout=5.0, follow_redirects=True, headers=headers) as client:
            res = client.get(target_url)
            status_code = res.status_code
            latency_ms = int((datetime.datetime.now() - start).total_seconds() * 1000)
    except Exception:
        status_code = 502
        latency_ms = 1200

    perf_score = max(40, min(99, 100 - int(latency_ms / 20)))
    seo_score = 92 if status_code == 200 else 45

    return {
        "status": "success",
        "url": target_url,
        "strategy": req.strategy,
        "data_source": "heuristic_estimate_pagespeed_unavailable",
        "scores": {
            "performance": perf_score,
            "seo": seo_score,
            # NOTE: PageSpeed Insights was unreachable/unavailable for this
            # request, so these two can't be measured — they keep the old
            # static defaults only as a rough placeholder (never a real
            # accessibility/best-practices audit), which is exactly why
            # data_source above says so explicitly instead of staying silent.
            "accessibility": 88,
            "best_practices": 90,
        },
        "metrics": {
            "first_contentful_paint": f"{round(latency_ms / 1000, 2)}s",
            "largest_contentful_paint": f"{round((latency_ms + 400) / 1000, 2)}s",
            "total_blocking_time": f"{max(10, latency_ms - 200)}ms",
            "cumulative_layout_shift": "0.04",
        },
    }


@router.post("/competitor/analyze")
def analyze_competitor_website(
    req: CompetitorRequest,
    current_user: dict = Depends(get_current_user_helper),
):
    comp_url = req.competitor_url.strip()
    if not comp_url.startswith("http"):
        comp_url = f"https://{comp_url}"

    title = "Competitor Domain"
    meta_desc = ""
    social_links = []
    detected_tech = []

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36"}
    html = ""
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(comp_url)
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.string:
                title = soup.title.string.strip()

            meta_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag.get("content").strip()

            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                if any(plat in href for plat in ["twitter.com", "x.com", "linkedin.com", "facebook.com", "instagram.com"]):
                    if a["href"] not in social_links:
                        social_links.append(a["href"])
    except Exception:
        pass

    # FIX: tech_stack used to be a hardcoded list regardless of what was
    # actually scraped. Now it's detected from real page signals only.
    if "_next/static" in html:
        detected_tech.append("Next.js (React)")
    elif re.search(r'\breact\b', html, re.I):
        detected_tech.append("React")
    if re.search(r'\bnuxt\b|\bvue\b', html, re.I):
        detected_tech.append("Vue.js / Nuxt")
    if "cloudflare" in html.lower() or "cf-ray" in html.lower():
        detected_tech.append("Cloudflare")
    if re.search(r'gtag\(|googletagmanager|G-[A-Z0-9]{6,}', html):
        detected_tech.append("Google Analytics 4")
    if "tailwind" in html.lower():
        detected_tech.append("Tailwind CSS")

    return {
        "status": "success",
        "competitor_url": comp_url,
        "title": title,
        "meta_description": meta_desc or "No meta description found.",
        "technology_stack": detected_tech or ["Undetected from static HTML (may be a client-rendered SPA)."],
        "data_source": "live_scrape",
        "social_presence": social_links or [],
        "swot": {
            "note": "SWOT generation requires an LLM (set GROQ_API_KEY) — showing detected facts only for now.",
            "detected_facts": {
                "has_meta_description": bool(meta_desc),
                "social_links_found": len(social_links),
                "detected_tech": detected_tech,
            },
        },
    }
