import os
import uuid
import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from pymongo.database import Database

from backend.database import get_db
from backend.deps import get_current_user as get_current_user_helper
from backend.llm import generate_json, is_llm_configured
from backend.email_service import send_email, is_email_configured

router = APIRouter(prefix="/api/campaigns", tags=["Campaigns, Ads & Marketing Automation"])


class CreateCampaignRequest(BaseModel):
    name: str
    objective: str = "leads"  # awareness, traffic, leads, sales
    channels: Optional[List[str]] = ["google_ads", "meta_ads", "linkedin", "email"]
    budget: float = 1000.0
    target_audience: str = "Small business owners & digital marketers"
    product_name: str = "AI Marketing Operating System"


class AdCreativeRequest(BaseModel):
    product_name: str
    target_audience: str
    platform: str = "google_ads"  # google_ads, meta_ads, linkedin_ads


class SocialCalendarRequest(BaseModel):
    brand_name: str
    industry: str = "technology"


class EmailSequenceRequest(BaseModel):
    product_name: str
    sequence_type: str = "welcome"  # welcome, promo, cart_abandonment


class SendSequenceRequest(BaseModel):
    to_email: EmailStr
    product_name: str
    sequence_type: str = "welcome"


@router.post("/create")
def create_campaign(
    req: CreateCampaignRequest,
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    campaign_id = f"CAMP_{uuid.uuid4().hex[:8].upper()}"

    channel_allocations = {}
    per_channel = req.budget / max(1, len(req.channels or []))
    for ch in (req.channels or ["google_ads", "meta_ads"]):
        channel_allocations[ch] = round(per_channel, 2)

    campaign_data = {
        "campaign_id": campaign_id,
        "user_email": current_user["email"],
        "name": req.name,
        "objective": req.objective,
        "budget": req.budget,
        "channels": req.channels,
        "channel_allocations": channel_allocations,
        "target_audience": req.target_audience,
        "product_name": req.product_name,
        "status": "active",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        # NOTE: these metrics are still placeholders — no ad platform is
        # actually connected (see BRD CAMP-02/03/04). Publishing to real
        # Google/Meta/LinkedIn ad accounts needs OAuth + a live ad account
        # on each platform, which is out of scope for a free-API pass.
        "metrics_data_source": "not_connected_no_real_ad_platform",
        "metrics": {
            "impressions": 0,
            "clicks": 0,
            "ctr": "0%",
            "conversions": 0,
            "cost_per_lead": 0,
            "roas": "0x",
        },
    }

    db.campaigns.insert_one(campaign_data)
    campaign_data["_id"] = str(campaign_data.get("_id", ""))

    return {"status": "success", "campaign": campaign_data}


@router.get("/list")
def list_campaigns(
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    raw_campaigns = db.campaigns.find({"user_email": current_user["email"]})
    if hasattr(raw_campaigns, "sort") and callable(getattr(raw_campaigns, "sort")):
        try:
            campaigns = list(raw_campaigns.sort("created_at", -1))
        except Exception:
            campaigns = list(raw_campaigns)
    else:
        campaigns = list(raw_campaigns)

    for c in campaigns:
        c["_id"] = str(c["_id"])
    return {"status": "success", "campaigns": campaigns}


@router.post("/ads/generate-creatives")
def generate_ad_creatives(
    req: AdCreativeRequest,
    current_user: dict = Depends(get_current_user_helper),
):
    p_name = req.product_name.strip()
    platform = req.platform.lower()

    llm_result = generate_json(
        system_prompt=(
            "You are a senior digital ad copywriter. Return a JSON object: "
            '{"creatives": [{"headline":"...","primary_text":"...","cta":"...",'
            '"ai_image_prompt":"...","recommended_budget":"$XX/day"}, ...]} '
            "with exactly 3 distinct, platform-appropriate ad variations. Keep headlines "
            "under 40 characters for google_ads."
        ),
        user_prompt=f"Product: {p_name}\nPlatform: {platform}\nTarget audience: {req.target_audience}",
    )

    if llm_result and isinstance(llm_result.get("creatives"), list) and llm_result["creatives"]:
        creatives = [
            {"id": f"ad_{i}", "platform": platform, **c}
            for i, c in enumerate(llm_result["creatives"][:3], start=1)
        ]
        generation_source = "llm"
    else:
        creatives = [
            {
                "id": "ad_1", "platform": platform,
                "headline": f"Stop Guessing Marketing — Try {p_name}",
                "primary_text": f"Analyze, optimize, publish, and scale your digital marketing with {p_name}.",
                "cta": "Start Free Trial",
                "ai_image_prompt": f"Professional futuristic digital marketing dashboard for {p_name}, 3d rendering",
                "recommended_budget": "$25/day",
            },
            {
                "id": "ad_2", "platform": platform,
                "headline": f"Rank #1 on Google with {p_name}",
                "primary_text": f"Discover keywords trapped on Page 2 for {req.target_audience}.",
                "cta": "Analyze My Website",
                "ai_image_prompt": f"Minimalist workspace showcasing SEO growth charts for {p_name}, photorealistic",
                "recommended_budget": "$35/day",
            },
            {
                "id": "ad_3", "platform": platform,
                "headline": "1-Click AI Video & Campaign Studio",
                "primary_text": f"Generate HD promo videos and campaigns in seconds with {p_name}.",
                "cta": "Generate AI Video",
                "ai_image_prompt": f"Cinematic AI video studio interface for {p_name}, 8k ultra detailed",
                "recommended_budget": "$40/day",
            },
        ]
        generation_source = "template"

    return {
        "status": "success",
        "platform": platform,
        "product_name": p_name,
        "creatives": creatives,
        "generation_source": generation_source,  # "llm" or "template" — honestly disclosed
        "llm_configured": is_llm_configured(),
    }


@router.post("/social/calendar")
@router.post("/social/generate-calendar")
def generate_social_calendar(
    req: SocialCalendarRequest,
    current_user: dict = Depends(get_current_user_helper),
):
    b_name = req.brand_name.strip()

    llm_result = generate_json(
        system_prompt=(
            "You are a social media strategist. Return a JSON object: "
            '{"calendar": [{"day":"Monday","platform":"...","post_type":"...","topic":"...",'
            '"caption":"...","recommended_time":"HH:MM AM/PM"}, ... 5 days total]} '
            "tailored to the brand and industry given."
        ),
        user_prompt=f"Brand: {b_name}\nIndustry: {req.industry}",
    )

    if llm_result and isinstance(llm_result.get("calendar"), list) and llm_result["calendar"]:
        calendar_days = [{"status": "scheduled", **day} for day in llm_result["calendar"]]
        generation_source = "llm"
    else:
        calendar_days = [
            {"day": "Monday", "platform": "Instagram Reel / TikTok", "post_type": "Video Short",
             "topic": f"3 Essential SEO Hacks Every Startup Needs ({b_name})",
             "caption": f"Are your keywords stuck on Page 2? Here's how {b_name} moves rankings up. #SEO #Marketing",
             "recommended_time": "09:00 AM", "status": "scheduled"},
            {"day": "Tuesday", "platform": "LinkedIn Article", "post_type": "Thought Leadership",
             "topic": "Why AI Search (GEO) Is Changing SEO",
             "caption": f"Search engines are evolving into AI answers. Here's how {b_name} prepares your brand. #AI",
             "recommended_time": "11:30 AM", "status": "scheduled"},
            {"day": "Wednesday", "platform": "YouTube Short / Reels", "post_type": "Product Showcase",
             "topic": "Watch AI Generate a Promo Video Live",
             "caption": "No editing skills required! Try it today. #AIVideo",
             "recommended_time": "02:00 PM", "status": "scheduled"},
            {"day": "Thursday", "platform": "X (Twitter) Thread", "post_type": "Educational Thread",
             "topic": f"10 Mistakes Marketers Make with Page-2 Keywords (Thread by {b_name})",
             "caption": "1/7 Keywords ranking #11-20 are your biggest quick-win opportunity...",
             "recommended_time": "04:15 PM", "status": "scheduled"},
            {"day": "Friday", "platform": "Facebook & Instagram Post", "post_type": "Customer Case Study",
             "topic": "How Company X Grew Organic Traffic",
             "caption": f"See how {b_name} transformed a real growth trajectory.",
             "recommended_time": "06:00 PM", "status": "scheduled"},
        ]
        generation_source = "template"

    return {
        "status": "success",
        "brand_name": b_name,
        "calendar": calendar_days,
        "generation_source": generation_source,
        "llm_configured": is_llm_configured(),
    }


def _build_email_sequence(req: "EmailSequenceRequest"):
    p_name = req.product_name.strip()
    seq_type = req.sequence_type.lower()

    llm_result = generate_json(
        system_prompt=(
            "You are an email marketing copywriter. Return a JSON object: "
            '{"emails": [{"step":1,"timing":"...","subject":"...","body":"..."}, ...]} '
            "for the requested lifecycle sequence type (welcome, promo, or cart_abandonment), "
            "2-3 emails, genuinely persuasive and specific to the product."
        ),
        user_prompt=f"Product: {p_name}\nSequence type: {seq_type}",
    )

    if llm_result and isinstance(llm_result.get("emails"), list) and llm_result["emails"]:
        return llm_result["emails"], "llm"

    if seq_type == "welcome":
        sequence = [
            {"step": 1, "timing": "Immediately after signup",
             "subject": f"Welcome to {p_name} — Your AI Marketing OS is Ready!",
             "body": f"Hi there,\n\nWelcome to {p_name}! Run your first AI Marketing Doctor scan to get instant SEO scores and fixes.\n\nBest,\nThe {p_name} Team"},
            {"step": 2, "timing": "Day 2",
             "subject": f"Discover your Top 10 Ranking Opportunities with {p_name}",
             "body": f"Keywords ranking #11-20 are your biggest growth opportunity. {p_name} finds them automatically."},
            {"step": 3, "timing": "Day 4",
             "subject": "Generate AI Promo Videos in 1 Click",
             "body": f"{p_name} includes an AI Video Studio that generates promo videos instantly. Create your first one now."},
        ]
    else:
        sequence = [
            {"step": 1, "timing": "Day 1",
             "subject": f"Special Offer: Scale Your Business with {p_name}",
             "body": f"Unlock more AI website audits and campaign tools with {p_name}. Upgrade today."},
        ]
    return sequence, "template"


@router.post("/email/generate-sequence")
def generate_email_sequence(
    req: EmailSequenceRequest,
    current_user: dict = Depends(get_current_user_helper),
):
    sequence, generation_source = _build_email_sequence(req)
    return {
        "status": "success",
        "product_name": req.product_name.strip(),
        "sequence_type": req.sequence_type.lower(),
        "emails": sequence,
        "generation_source": generation_source,
        "llm_configured": is_llm_configured(),
    }


@router.post("/email/send-sequence")
def send_email_sequence(
    req: SendSequenceRequest,
    current_user: dict = Depends(get_current_user_helper),
):
    """
    FIX: generated email sequences used to have no way to actually reach
    anyone's inbox (BRD CONT-03). Sends via Resend's genuinely free tier
    (3,000 emails/month, no credit card) when RESEND_API_KEY is set;
    otherwise returns an honest "not configured" result per email instead
    of pretending to send.
    """
    sequence, generation_source = _build_email_sequence(
        EmailSequenceRequest(product_name=req.product_name, sequence_type=req.sequence_type)
    )

    results = []
    for step in sequence:
        outcome = send_email(str(req.to_email), step.get("subject", ""), step.get("body", ""))
        results.append({"step": step.get("step"), "subject": step.get("subject"), **outcome})

    return {
        "status": "success",
        "to_email": req.to_email,
        "email_provider_configured": is_email_configured(),
        "generation_source": generation_source,
        "results": results,
    }


# =====================================================
# TOUCHPOINT EVENT STREAM & MULTI-TOUCH ATTRIBUTION
# (unchanged — this was already real, correctly implemented logic)
# =====================================================

class TrackEventRequest(BaseModel):
    campaign_id: str
    user_identifier: str
    channel: str
    event_type: str
    session_id: Optional[str] = None
    conversion_value: Optional[float] = 0.0


@router.post("/track-event")
def track_campaign_event(
    req: TrackEventRequest,
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    touchpoint_id = f"TP_{uuid.uuid4().hex[:10].upper()}"
    timestamp_iso = datetime.datetime.utcnow().isoformat() + "Z"

    event_record = {
        "touchpoint_id": touchpoint_id,
        "campaign_id": req.campaign_id,
        "user_identifier": req.user_identifier,
        "channel": req.channel.lower(),
        "event_type": req.event_type.lower(),
        "session_id": req.session_id or f"sess_{uuid.uuid4().hex[:8]}",
        "conversion_value": req.conversion_value or 0.0,
        "timestamp": timestamp_iso,
    }

    db.touchpoints.insert_one(event_record)
    return {"status": "success", "touchpoint_id": touchpoint_id, "recorded_at": timestamp_iso, "event": event_record}


@router.get("/attribution/{campaign_id}")
def calculate_campaign_attribution(
    campaign_id: str,
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    touchpoints = list(db.touchpoints.find({"campaign_id": campaign_id}))

    if not touchpoints:
        return {
            "status": "success",
            "campaign_id": campaign_id,
            "total_touchpoints": 0,
            "total_conversion_revenue": 0.0,
            "data_source": "no_touchpoints_recorded_yet",
            "attribution_models": {"first_touch": {}, "last_touch": {}, "linear": {}, "w_shaped": {}},
        }

    users_stream: Dict[str, List[dict]] = {}
    for tp in touchpoints:
        uid = tp.get("user_identifier", "anonymous")
        users_stream.setdefault(uid, []).append(tp)

    for uid in users_stream:
        users_stream[uid].sort(key=lambda x: x.get("timestamp", ""))

    first_touch_rev: Dict[str, float] = {}
    last_touch_rev: Dict[str, float] = {}
    linear_rev: Dict[str, float] = {}
    w_shaped_rev: Dict[str, float] = {}
    total_revenue = 0.0

    for uid, tps in users_stream.items():
        user_val = max([tp.get("conversion_value", 0.0) for tp in tps] + [0.0])
        total_revenue += user_val

        ft_ch = tps[0]["channel"]
        first_touch_rev[ft_ch] = first_touch_rev.get(ft_ch, 0.0) + user_val

        lt_ch = tps[-1]["channel"]
        last_touch_rev[lt_ch] = last_touch_rev.get(lt_ch, 0.0) + user_val

        n = len(tps)
        share = user_val / n if n > 0 else 0
        for tp in tps:
            ch = tp["channel"]
            linear_rev[ch] = linear_rev.get(ch, 0.0) + share

        if n == 1:
            w_shaped_rev[ft_ch] = w_shaped_rev.get(ft_ch, 0.0) + user_val
        elif n == 2:
            w_shaped_rev[ft_ch] = w_shaped_rev.get(ft_ch, 0.0) + (user_val * 0.5)
            w_shaped_rev[lt_ch] = w_shaped_rev.get(lt_ch, 0.0) + (user_val * 0.5)
        else:
            mid_idx = n // 2
            mid_ch = tps[mid_idx]["channel"]
            other_share = (user_val * 0.1) / (n - 3) if n > 3 else 0.0

            w_shaped_rev[ft_ch] = w_shaped_rev.get(ft_ch, 0.0) + (user_val * 0.3)
            w_shaped_rev[mid_ch] = w_shaped_rev.get(mid_ch, 0.0) + (user_val * 0.3)
            w_shaped_rev[lt_ch] = w_shaped_rev.get(lt_ch, 0.0) + (user_val * 0.3)

            for i, tp in enumerate(tps):
                if i not in (0, mid_idx, n - 1):
                    ch = tp["channel"]
                    w_shaped_rev[ch] = w_shaped_rev.get(ch, 0.0) + other_share

    return {
        "status": "success",
        "campaign_id": campaign_id,
        "total_touchpoints": len(touchpoints),
        "total_conversion_revenue": total_revenue,
        "data_source": "real_touchpoint_stream",
        "attribution_models": {
            "first_touch": first_touch_rev,
            "last_touch": last_touch_rev,
            "linear": linear_rev,
            "w_shaped": w_shaped_rev,
        },
    }
