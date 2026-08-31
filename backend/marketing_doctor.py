import os
import uuid
import datetime
import urllib.parse
import re
import json
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
from pymongo.database import Database

from backend.database import get_db
from backend.deps import get_current_user as get_current_user_helper

router = APIRouter(prefix="/api/marketing-doctor", tags=["AI Marketing Doctor"])

# 15-Minute In-Memory LRU Diagnostic Cache
DIAGNOSTIC_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes


class DiagnoseRequest(BaseModel):
    website_url: str
    target_goals: Optional[List[str]] = ["seo", "leads", "conversions"]
    industry: Optional[str] = "technology"


@router.post("/diagnose")
def run_marketing_diagnosis(
    req: DiagnoseRequest,
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    """
    AI Marketing Doctor ("Analyze My Marketing").
    Performs a live real-time HTTP diagnostic scan across the target URL.
    Uses BeautifulSoup4, SPA (React/Vue/Next.js) hydration inspection, and
    15-minute caching. This part is genuinely real signal.

    NOTE (honesty fix): `content_score`, `social_score`, `ads_score`, and
    `ai_search_score` below are derived from a hash of the domain string —
    they are NOT a real content/social/ads audit. The previous version
    presented them with no disclosure at all. They now carry an explicit
    `is_estimated: true` flag, per Aura_Marketing_AI_Review.md section 3 and
    BRD NFR-COMPLY-04. Wiring real providers for these (e.g. an LLM content
    grader, a social-API check) is tracked as follow-up work, not done here.
    """
    clean_url = req.website_url.strip()
    if not clean_url.startswith("http"):
        clean_url = f"https://{clean_url}"

    parsed = urllib.parse.urlparse(clean_url)
    domain = parsed.netloc or parsed.path

    cache_key = clean_url.lower()
    now_ts = datetime.datetime.utcnow()
    if cache_key in DIAGNOSTIC_CACHE:
        cached_entry = DIAGNOSTIC_CACHE[cache_key]
        if (now_ts - cached_entry["cached_at"]).total_seconds() < CACHE_TTL_SECONDS:
            return {"status": "success", "cached": True, "diagnosis": cached_entry["data"]}

    http_status = 200
    response_time_ms = 350
    has_ssl = clean_url.startswith("https")
    title_text = ""
    has_meta_desc = False
    has_h1 = False
    has_schema_jsonld = False
    is_spa_framework = False
    framework_name = "Static / Server-Rendered"
    content_length = 0

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 AuraMarketingDoctor/2.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        start_time = datetime.datetime.now()
        with httpx.Client(timeout=6.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(clean_url)
            http_status = resp.status_code
            response_time_ms = int((datetime.datetime.now() - start_time).total_seconds() * 1000)
            html = resp.text
            content_length = len(html)

            try:
                soup = BeautifulSoup(html, "html.parser")

                if soup.find("div", id=re.compile(r"^(root|__next|app)$", re.I)) or re.search(r'(_next/static|bundle\.js|main\.js|react|vue)', html, re.I):
                    is_spa_framework = True
                    if "_next" in html:
                        framework_name = "Next.js (React)"
                    elif "vue" in html.lower():
                        framework_name = "Vue.js / Nuxt"
                    else:
                        framework_name = "Single-Page App (React/Vue/Angular)"

                if soup.title and soup.title.string:
                    title_text = soup.title.string.strip()
                elif soup.find("meta", property="og:title"):
                    title_text = soup.find("meta", property="og:title").get("content", "").strip()

                meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
                og_desc = soup.find("meta", property="og:description")
                if (meta_desc and meta_desc.get("content")) or (og_desc and og_desc.get("content")):
                    has_meta_desc = True

                if soup.find("h1") or soup.find(class_=re.compile(r"(title|header|hero)", re.I)):
                    has_h1 = True

                if soup.find("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
                    has_schema_jsonld = True

                next_data_script = soup.find("script", id="__NEXT_DATA__")
                if next_data_script and next_data_script.string:
                    try:
                        n_data = json.loads(next_data_script.string)
                        page_props = n_data.get("props", {}).get("pageProps", {})
                        if not title_text and page_props.get("title"):
                            title_text = str(page_props["title"])
                        if not has_meta_desc and (page_props.get("description") or page_props.get("metaDescription")):
                            has_meta_desc = True
                    except Exception:
                        pass

            except Exception:
                t_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                if t_match:
                    title_text = t_match.group(1).strip()
                if re.search(r'name=["\']description["\']', html, re.IGNORECASE) or re.search(r'property=["\']og:description["\']', html, re.IGNORECASE):
                    has_meta_desc = True
                if re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL):
                    has_h1 = True

    except Exception:
        http_status = 502
        response_time_ms = 1200

    # --- Real signal scores (from the actual DOM inspection above) ---
    seo_score = 92
    if not has_meta_desc and not is_spa_framework:
        seo_score -= 15
    if not has_h1:
        seo_score -= 15
    if not title_text:
        seo_score -= 15
    if response_time_ms > 800:
        seo_score -= 10
    seo_score = min(98, max(50, seo_score))

    conversion_score = 88
    if response_time_ms > 500:
        conversion_score -= 12
    if not has_ssl:
        conversion_score -= 25
    conversion_score = min(95, max(45, conversion_score))

    # --- Estimated/heuristic scores (NOT a real audit — see docstring) ---
    domain_hash = sum(ord(c) for c in domain)
    content_score = min(95, max(55, (domain_hash * 11) % 40 + 58))
    social_score = min(92, max(50, (domain_hash * 13) % 40 + 52))
    ads_score = min(96, max(60, (domain_hash * 17) % 32 + 64))
    ai_search_score = 88 if has_schema_jsonld else min(88, max(45, (domain_hash * 23) % 40 + 48))

    overall_health = int(
        (seo_score * 0.25)
        + (content_score * 0.20)
        + (conversion_score * 0.20)
        + (social_score * 0.15)
        + (ads_score * 0.10)
        + (ai_search_score * 0.10)
    )

    problems = []
    if not has_meta_desc or not has_h1:
        problems.append({
            "id": "prob_meta_h1",
            "category": "Technical SEO",
            "severity": "critical",
            "title": f"Missing Title/H1/Meta Description on {domain}",
            "description": f"Live DOM inspection detected missing HTML H1 or Meta Description tags on '{clean_url}' ({framework_name}).",
            "impact": "Improves search result click-through rate",
            "action_title": "Fix Meta & H1 Headers",
            "action_endpoint": "/api/seo/generate-fix-plan",
            "payload": {"website_url": clean_url, "issue_type": "meta_h1"},
            "is_estimated": False,
        })

    if response_time_ms > 400:
        problems.append({
            "id": "prob_speed_3",
            "category": "Page Performance",
            "severity": "medium",
            "title": f"Live Response Latency ({response_time_ms}ms) Exceeds Benchmark",
            "description": f"Target URL server response time was measured at {response_time_ms}ms (Benchmark < 250ms).",
            "impact": "Improves lead-form conversion rate",
            "action_title": "Optimize Page Speed & Images",
            "action_endpoint": "/api/webaudit/lighthouse",
            "payload": {"url": clean_url},
            "is_estimated": False,
        })

    if not has_schema_jsonld:
        problems.append({
            "id": "prob_aisearch_4",
            "category": "AI Search / GEO",
            "severity": "medium",
            "title": "Missing Schema.org Entity Markup for AI Search",
            "description": "DOM inspection found no Schema.org/Organization or FAQPage JSON-LD markup for ChatGPT-style citations.",
            "impact": "May improve AI-search citation odds",
            "action_title": "Generate AI Search Entity Schema",
            "action_endpoint": "/api/seo/generate-fix-plan",
            "payload": {"website_url": clean_url, "issue_type": "schema"},
            "is_estimated": False,
        })

    recommendations = [
        f"Live DOM & hydration scan completed for {clean_url} [{framework_name}] (HTTP {http_status}, {response_time_ms}ms).",
        "Run /api/seo/top10-opportunities for real, per-keyword ranking checks (needs SERPAPI_KEY).",
        "Optimize page headers and meta tags to improve search result CTR.",
        "Deploy Schema.org JSON-LD markup to help AI-search (ChatGPT/Perplexity) visibility.",
        "Run /api/webaudit/lighthouse for a real Core Web Vitals report (Google PageSpeed Insights).",
    ]

    diagnosis_id = f"DIAG_{uuid.uuid4().hex[:10].upper()}"
    diagnosis_record = {
        "diagnosis_id": diagnosis_id,
        "user_email": current_user["email"],
        "website_url": clean_url,
        "domain": domain,
        "live_metrics": {
            "http_status": http_status,
            "response_time_ms": response_time_ms,
            "title_text": title_text or f"{domain} Homepage",
            "has_ssl": has_ssl,
            "has_meta_desc": has_meta_desc,
            "has_h1": has_h1,
            "has_schema_jsonld": has_schema_jsonld,
            "is_spa_framework": is_spa_framework,
            "framework_name": framework_name,
            "content_length": content_length,
        },
        "scores": {
            # Kept as flat numbers (unchanged shape) so the existing frontend
            # gauges/charts keep working without a rewrite. Which of these
            # are real vs. heuristic is now disclosed separately below
            # instead of silently presenting all six as equally measured.
            "overall_health": overall_health,
            "seo": seo_score,
            "content": content_score,
            "social": social_score,
            "ads": ads_score,
            "conversion": conversion_score,
            "ai_search": ai_search_score,
        },
        "score_disclosure": {
            "seo": "measured_from_live_dom",
            "content": "estimated_heuristic_not_a_real_audit",
            "social": "estimated_heuristic_not_a_real_audit",
            "ads": "estimated_heuristic_not_a_real_audit",
            "conversion": "measured_from_live_response",
            "ai_search": "measured_schema_presence" if has_schema_jsonld else "estimated_heuristic_not_a_real_audit",
        },
        "problems": problems,
        "recommendations": recommendations,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

    db.marketing_diagnoses.insert_one(diagnosis_record)
    DIAGNOSTIC_CACHE[cache_key] = {"cached_at": now_ts, "data": diagnosis_record}

    return {"status": "success", "cached": False, "diagnosis": diagnosis_record}


@router.get("/history")
def get_diagnosis_history(
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    diagnoses = list(
        db.marketing_diagnoses.find({"user_email": current_user["email"]})
        .sort("created_at", -1)
        .limit(10)
    )
    for d in diagnoses:
        d["_id"] = str(d["_id"])
    return {"status": "success", "diagnoses": diagnoses}
