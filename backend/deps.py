"""
Shared authentication dependency for every router.

This replaces the per-router `get_current_user_helper` that used to be
copy-pasted into every file (auth_router, wallet_router, image_router,
webaudit_router, analytics_router, marketing_doctor, seo_engine, campaigns).
That old helper silently fell back to a hardcoded `demo.user@aura.com`
account with 9999 tokens whenever no/invalid bearer token was supplied,
which meant every paid feature in this API was usable by anyone, without
logging in or paying. See Aura_Marketing_AI_Review.md, section 4.

get_current_user() below has NO anonymous fallback: it always requires a
valid, non-expired JWT for a user that still exists in the database.
"""
from fastapi import Depends, HTTPException, status, Header
from pymongo.database import Database

from backend.database import get_db
from backend.auth import decode_access_token


def get_current_user(authorization: str = Header(None), db: Database = Depends(get_db)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token. Log in and send 'Authorization: Bearer <token>'.",
        )

    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    user = db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists.")

    return user

# ---------------------------------------------------------------------------
# Shared token-metering helper.
#
# FIX: a manual click-through test found that Website Audit, Competitor
# Intel, Content Studio, Social Studio, Ads Generator, and Email Marketing
# all advertise a token cost in the UI (e.g. "10 TOKENS") but never actually
# charged anything -- only /api/video/generate deducted tokens. This shared
# helper is now used by those routes so the wallet behaves consistently:
# every paid action either charges correctly or is rejected for
# insufficient balance, and always records a real transaction.
# ---------------------------------------------------------------------------
import datetime
import uuid


def charge_tokens(db, current_user: dict, amount: int, tier_name: str, payment_method: str) -> int:
    """Deducts `amount` tokens from current_user and records a transaction.

    Raises HTTP 402 if the user doesn't have enough tokens. Returns the
    token balance remaining after the charge.
    """
    current_tokens = current_user.get("tokens", 0)
    if current_tokens < amount:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient tokens. This action requires {amount} tokens, you have {current_tokens}.",
        )

    tx_id = f"TX_{tier_name.upper().replace(' ', '_')}_{uuid.uuid4().hex[:10]}"
    db.users.update_one(
        {"email": current_user["email"]},
        {
            "$inc": {"tokens": -amount},
            "$push": {"transactions": {
                "transaction_id": tx_id,
                "tier_name": tier_name,
                "amount": -amount,
                "price": 0.0,
                "payment_method": payment_method,
                "status": "success",
                "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            }},
        },
    )
    return current_tokens - amount

