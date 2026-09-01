"""
Real, free-tier LLM-backed content generation.

Uses Groq (https://console.groq.com) — genuinely free, no credit card
required, OpenAI-compatible chat completion API, fast Llama models. If
GROQ_API_KEY isn't set, every function below returns None so callers can
fall back to their existing static templates instead of crashing.

Every response from a caller that uses this module should set
`"generation_source": "llm"` when this returns data and `"template"` when
it falls back — see Aura_Marketing_AI_Review.md ("No LLM anywhere") and
BRD NFR-COMPLY-04 (disclose simulated output).
"""
import os
import json
import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# FIX: the old default (llama-3.3-70b-versatile) has been removed from
# Groq'''s model catalog -- every LLM call was returning 404 model_not_found
# and silently falling back to templates (confirmed live against the
# account'''s actual key: GET /openai/v1/models no longer lists it). Verified
# openai/gpt-oss-120b is live on this account and returns well-formed JSON
# via response_format=json_object. If GROQ_MODEL is unset, this default is
# now used instead of the dead one.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def is_llm_configured() -> bool:
    return bool(GROQ_API_KEY)


def generate_json(system_prompt: str, user_prompt: str, max_tokens: int = 900):
    """
    Calls Groq and asks for a JSON object back. Returns a dict on success,
    or None on any failure/misconfiguration — never raises, so callers can
    always fall back safely.
    """
    if not GROQ_API_KEY:
        return None
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt + "\nRespond with ONLY a valid JSON object, no prose, no markdown fences."},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception as e:
        print(f"[llm] Groq generation failed, falling back to templates: {e}")
        return None
