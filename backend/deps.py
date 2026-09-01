"""
Shared authentication and RBAC dependency for every router.
"""
import datetime
import uuid
from typing import List
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


def require_role(allowed_roles: List[str]):
    """RBAC dependency factory that enforces allowed roles (owner, marketer, viewer)."""
    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", "owner").lower()
        if user_role not in [r.lower() for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action forbidden for role '{user_role}'. Required role: {allowed_roles}",
            )
        return current_user
    return role_checker


def require_verified_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Enforces email verification before accessing sensitive/paid features."""
    if not current_user.get("is_verified", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified. Please click the verification link sent to your email.",
        )
    return current_user


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
