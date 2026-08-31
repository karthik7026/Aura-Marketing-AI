"""
Real email sending via Resend (https://resend.com) — genuinely free tier:
3,000 emails/month, 100/day, no credit card required. Replaces the old
behavior where "generated" email sequences were never actually sendable
to anyone (BRD CONT-03).

Needs RESEND_API_KEY. RESEND_FROM_EMAIL can stay as the Resend sandbox
sender (onboarding@resend.dev) until a custom domain is verified.
"""
import os
import httpx

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")


def is_email_configured() -> bool:
    return bool(RESEND_API_KEY)


def send_email(to_email: str, subject: str, body_text: str) -> dict:
    if not RESEND_API_KEY:
        return {
            "sent": False,
            "reason": "RESEND_API_KEY not configured. Get a free key at https://resend.com "
                      "(3,000 emails/month free, no credit card) and set RESEND_API_KEY in .env.",
        }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": RESEND_FROM_EMAIL, "to": [to_email], "subject": subject, "text": body_text},
            )
            resp.raise_for_status()
            return {"sent": True, "provider_id": resp.json().get("id")}
    except Exception as e:
        return {"sent": False, "reason": str(e)}
