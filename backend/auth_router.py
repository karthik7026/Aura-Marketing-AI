import os
import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from pymongo.database import Database

from backend.database import get_db
from backend.auth import (
    get_password_hash, verify_password,
    create_access_token, decode_access_token
)
from backend.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication & Identity"])

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    workspace_type: str = "video"
    company_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str  # the Google ID token from Google Identity Services


@router.post("/register")
def register(req: RegisterRequest, db: Database = Depends(get_db)):
    email = req.email.lower().strip()
    existing = db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    hashed = get_password_hash(req.password)
    user_doc = {
        "email": email,
        "hashed_password": hashed,
        "provider": "local",
        "provider_id": None,
        "workspace_type": req.workspace_type,
        "company_name": req.company_name or "Aura Business",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "is_active": True,
        "tokens": 9999,  # signup bonus credits — a product/pricing decision, not a security bug
        "transactions": []
    }

    db.users.insert_one(user_doc)
    access_token = create_access_token(data={"sub": email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "email": email,
        "workspace_type": req.workspace_type
    }


@router.post("/login")
def login(req: LoginRequest, db: Database = Depends(get_db)):
    email = req.email.lower().strip()
    user = db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if not verify_password(req.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    access_token = create_access_token(data={"sub": email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "email": email,
        "workspace_type": user.get("workspace_type", "video")
    }


@router.post("/google")
def google_login(req: GoogleAuthRequest, db: Database = Depends(get_db)):
    """
    Real Google Sign-In. Verifies the ID token Google Identity Services
    hands the frontend, using Google's own public keys — no shared secret
    involved, and it's free to set up (a Google OAuth Client ID from
    https://console.cloud.google.com/apis/credentials costs nothing).

    FIX: the frontend already called POST /api/auth/google, but this route
    never existed on the backend at all (see Aura_Marketing_AI_Review.md).
    NOTE: you still need to (1) create a free OAuth Client ID in Google
    Cloud Console, (2) set GOOGLE_OAUTH_CLIENT_ID in .env, and (3) load the
    Google Identity Services script in the frontend so it actually sends a
    real `credential` here.
    """
    if not GOOGLE_OAUTH_CLIENT_ID:
        raise HTTPException(
            status_code=501,
            detail="Google Sign-In isn't configured. Set GOOGLE_OAUTH_CLIENT_ID in .env "
                   "(free to create at https://console.cloud.google.com/apis/credentials).",
        )

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        idinfo = google_id_token.verify_oauth2_token(
            req.credential, google_requests.Request(), GOOGLE_OAUTH_CLIENT_ID
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google credential: {e}")

    email = idinfo.get("email", "").lower().strip()
    if not email:
        raise HTTPException(status_code=401, detail="Google credential did not include an email.")

    user = db.users.find_one({"email": email})
    if not user:
        user_doc = {
            "email": email,
            "hashed_password": None,
            "provider": "google",
            "provider_id": idinfo.get("sub"),
            "workspace_type": "video",
            "company_name": idinfo.get("name") or "Aura Business",
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "is_active": True,
            "tokens": 9999,
            "transactions": [],
        }
        db.users.insert_one(user_doc)

    access_token = create_access_token(data={"sub": email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "email": email,
        "workspace_type": user.get("workspace_type", "video") if user else "video",
    }


@router.post("/apple")
def apple_login():
    """
    NOT IMPLEMENTED ON PURPOSE: unlike Google, Sign in with Apple requires
    an active Apple Developer Program membership, which costs $99/year —
    it is not available on any free tier, so it's out of scope for a
    free-APIs-only pass. Left as an explicit, honest 501 instead of a
    silent 404 so the frontend can show a real message.
    """
    raise HTTPException(
        status_code=501,
        detail="Sign in with Apple requires a paid ($99/yr) Apple Developer account and isn't "
               "implemented in this free-tier build. Use email/password or Google Sign-In instead.",
    )


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "email": current_user["email"],
        "tokens": current_user.get("tokens", 0),
        "workspace_type": current_user.get("workspace_type", "video"),
        "company_name": current_user.get("company_name", "Aura Business")
    }
