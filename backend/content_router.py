"""
AI Copywriting / Content Studio / Social Studio / Email Marketing (single-shot draft).

FIX: a manual click-through test found three frontend pages -- Content
Studio ("Draft Copywriting Asset"), Social Studio ("Generate Post Copy"),
and Email Marketing's single-draft flow ("Draft Email Newsletter") -- all
called POST /api/marketing/process, which does not exist anywhere on the
backend (confirmed 404), so all three silently did nothing. There was also
no real generation logic anywhere in the codebase for any of them
(generator.py is video-only despite its generic name; the *lifecycle*
email/social endpoints in campaigns.py are a different feature -- a
5-day content calendar / a 2-3 step drip sequence -- not a single ad-hoc
draft from a one-line brief).

This router adds the missing single-shot generation endpoint for real,
following the same LLM-first / honest-template-fallback pattern already
used in campaigns.py and llm.py: tries Groq first via generate_json(),
and falls back to a clearly-labeled static template if GROQ_API_KEY isn't
set, always disclosing which one produced the result via
`generation_source`.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from pymongo.database import Database

from backend.database import get_db
from backend.deps import get_current_user as get_current_user_helper, charge_tokens
from backend.llm import generate_json, is_llm_configured

router = APIRouter(prefix="/api/content", tags=["Content Studio"])

# FIX: matches each Studio page's advertised token cost in the UI, which
# previously charged nothing at all because the button called a 404.
CONTENT_TYPE_COSTS = {
    "blog": 5, "product": 5, "landing": 5, "faq": 5,   # Content Studio: "AI COPYWRITING (5 TOKENS)"
    "social_post": 2,                                    # Social Studio: "SOCIAL POST GENERATOR (2 TOKENS)"
    "email_newsletter": 2,                               # Email Marketing: "EMAIL CAMPAIGN BUILDER (2 TOKENS)"
}

CONTENT_TYPE_LABELS = {
    "blog": "SEO Blog Article",
    "product": "Product Description",
    "landing": "Landing Page Copy",
    "faq": "FAQ List",
    "social_post": "Social Media Post",
    "email_newsletter": "Email Newsletter",
}


class ContentGenerateRequest(BaseModel):
    content_type: str = "blog"   # blog, product, landing, faq, social_post, email_newsletter
    tone: str = "professional"   # professional, friendly, bold, formal
    brief: str = ""              # what the content should cover
    subject: str = ""            # optional subject line override (email_newsletter only)


def _template_fallback(content_type: str, tone: str, brief: str, subject: str) -> dict:
    topic = brief.strip() or "your product"
    label = CONTENT_TYPE_LABELS.get(content_type, "Content")

    if content_type == "faq":
        body = (
            f"Q: What is {topic}?\nA: {topic} helps you get results faster, with a "
            f"{tone} approach built for real-world use.\n\n"
            f"Q: Who is {topic} for?\nA: Teams and individuals who want a straightforward, "
            "no-nonsense way to get this done.\n\n"
            f"Q: How do I get started with {topic}?\nA: Sign up, complete the first guided step, "
            "and you'll see results within your first session."
        )
        return {"title": f"{label}: {topic}", "body": body}

    if content_type == "product":
        body = (
            f"{topic} — built to work the way you actually work. "
            f"Written in a {tone} tone, this description highlights what matters: "
            "clear benefits, no fluff, and a reason to act now."
        )
        return {"title": f"{label}: {topic}", "body": body}

    if content_type == "landing":
        body = (
            f"Headline: Meet {topic}.\n\n"
            f"Subheadline: The {tone} way to get this done, without the usual friction.\n\n"
            "CTA: Get Started Free"
        )
        return {"title": f"{label}: {topic}", "body": body}

    if content_type == "social_post":
        return {
            "title": f"{label}: {topic}",
            "post": f"{topic}\n\nWritten in a {tone} tone — a template fallback, not an LLM draft, "
                    "because GROQ_API_KEY isn't configured. Add it for a genuinely written post.",
            "hashtags": ["#marketing", "#smallbusiness"],
            "platform": "Instagram / Facebook",
            "best_time": "Not estimated (template fallback, no real audience data)",
        }

    if content_type == "email_newsletter":
        subj = subject.strip() or f"An update about {topic}"
        return {
            "title": subj,
            "subject": subj,
            "body": f"Hi there,\n\n{topic}\n\nThis is a template fallback, not an LLM-written draft, "
                    "because GROQ_API_KEY isn't configured. Add it to get a genuinely written email.\n\n"
                    f"Written in a {tone} tone.\n\nBest,\nThe Team",
            "cta": "Learn More",
        }

    # blog (default)
    body = (
        f"# {topic}\n\n"
        f"Here's a {tone}, practical look at {topic} and why it matters right now. "
        "This draft is a starting point — a template fallback, not an LLM-generated draft, "
        "because GROQ_API_KEY isn't configured. Add it to get a genuinely written article "
        "instead of this placeholder."
    )
    return {"title": f"{label}: {topic}", "body": body}


def _llm_prompts(content_type: str, tone: str, label: str) -> tuple:
    if content_type == "social_post":
        system = (
            f"You are a social media copywriter. Write one punchy {tone}-tone social post. "
            'Return a JSON object: {"post":"...","hashtags":["...", ...],"platform":"...",'
            '"best_time":"HH:MM AM/PM"} with 3-5 relevant hashtags and a sensible platform '
            "and posting time recommendation."
        )
    elif content_type == "email_newsletter":
        system = (
            f"You are an email marketing copywriter. Write one {tone}-tone newsletter/promo email. "
            'Return a JSON object: {"subject":"...","body":"...","cta":"..."} — body should be a '
            "genuinely persuasive, complete email, not a fragment."
        )
    else:
        system = (
            f"You are a professional copywriter. Write a {label} in a {tone} tone of voice. "
            'Return a JSON object: {"title": "...", "body": "..."} — the body should be genuinely '
            "useful, specific to the brief given, and appropriately long for the content type "
            "(a full blog article for 'blog', a short punchy paragraph for 'product', etc.)."
        )
    return system


@router.post("/generate")
def generate_content(
    req: ContentGenerateRequest,
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    content_type = req.content_type if req.content_type in CONTENT_TYPE_LABELS else "blog"
    cost = CONTENT_TYPE_COSTS.get(content_type, 5)
    tokens_remaining = charge_tokens(db, current_user, cost, CONTENT_TYPE_LABELS[content_type], f"content_generate_{content_type}")

    label = CONTENT_TYPE_LABELS[content_type]
    brief = req.brief.strip()
    system_prompt = _llm_prompts(content_type, req.tone, label)

    # FIX: long-form types (a full blog article, a multi-question FAQ list)
    # need more completion budget than the shared 1600-token default -- the
    # Groq model in use (openai/gpt-oss-120b) is a reasoning model that
    # spends tokens "thinking" before it writes the JSON body, and at a
    # tighter budget it was hitting Groq's json_validate_failed / "max
    # completion tokens reached before generating a valid document" error
    # and silently falling back to the template every time for these two
    # types specifically (confirmed live against the real API).
    llm_max_tokens = 2800 if content_type in ("blog", "faq") else 1600

    llm_result = generate_json(
        system_prompt=system_prompt,
        max_tokens=llm_max_tokens,
        user_prompt=(
            f"Content type: {label}\nTone: {req.tone}\n"
            f"Subject line (if provided): {req.subject or '(none given)'}\n"
            f"Brief: {brief or '(no brief given — use your best judgment)'}"
        ),
    )

    def _llm_ok() -> bool:
        if not llm_result:
            return False
        if content_type == "social_post":
            return bool(llm_result.get("post"))
        if content_type == "email_newsletter":
            return bool(llm_result.get("body"))
        return bool(llm_result.get("title") and llm_result.get("body"))

    if _llm_ok():
        result = llm_result
        generation_source = "llm"
    else:
        result = _template_fallback(content_type, req.tone, brief, req.subject)
        generation_source = "template"

    response = {
        "status": "success",
        "content_type": content_type,
        "tone": req.tone,
        "generation_source": generation_source,
        "llm_configured": is_llm_configured(),
        "tokens_remaining": tokens_remaining,
    }
    response.update(result)
    return response
