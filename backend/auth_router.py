import os
import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from typing import Optional
from pymongo.database import Database

from backend.database import get_db
from backend.auth import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token, decode_access_token
)
from backend.deps import get_current_user
from backend.email_service import send_email

router = APIRouter(prefix="/api/auth", tags=["Authentication & Identity"])

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "https://auradigimarketing.netlify.app").rstrip("/")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    workspace_type: str = "marketing"
    company_name: Optional[str] = None
    role: str = "owner"  # owner, marketer, viewer


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class GoogleAuthRequest(BaseModel):
    credential: str


@router.post("/register")
def register(req: RegisterRequest, db: Database = Depends(get_db)):
    email = req.email.lower().strip()
    existing = db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    hashed = get_password_hash(req.password)
    verify_token = uuid.uuid4().hex + uuid.uuid4().hex
    user_role = req.role.lower() if req.role.lower() in ["owner", "marketer", "viewer"] else "owner"

    user_doc = {
        "email": email,
        "hashed_password": hashed,
        "provider": "local",
        "provider_id": None,
        "workspace_type": req.workspace_type,
        "company_name": req.company_name or "Aura Business",
        "role": user_role,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "is_active": True,
        "is_verified": False,
        "verify_token": verify_token,
        "tokens": 9999,
        "transactions": []
    }

    db.users.insert_one(user_doc)

    # Send Verification Email via Resend
    verify_url = f"{FRONTEND_BASE_URL}/verify-email?token={verify_token}"
    email_body = f"Welcome to Aura Marketing AI OS!\n\nPlease verify your email address by clicking the link below:\n{verify_url}\n\nThank you!"
    send_email(email, "Verify Your Aura Account", email_body)

    access_token = create_access_token(data={"sub": email, "role": user_role})
    refresh_token = create_refresh_token(data={"sub": email})

    # Save Refresh Token
    db.refresh_tokens.insert_one({
        "email": email,
        "refresh_token": refresh_token,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z"
    })

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "email": email,
        "role": user_role,
        "workspace_type": req.workspace_type,
        "is_verified": False,
        "verification_url": verify_url
    }


@router.get("/verify-email")
def verify_email(token: str = Query(...), db: Database = Depends(get_db)):
    """AUTH-01: Verifies email token and activates account."""
    user = db.users.find_one({"verify_token": token})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token.")

    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True}, "$unset": {"verify_token": ""}}
    )
    return {"message": "Email successfully verified! You can now log in.", "verified": True}


@router.post("/login")
def login(req: LoginRequest, db: Database = Depends(get_db)):
    email = req.email.lower().strip()
    user = db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if not verify_password(req.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    user_role = user.get("role", "owner")
    access_token = create_access_token(data={"sub": email, "role": user_role})
    refresh_token = create_refresh_token(data={"sub": email})

    db.refresh_tokens.insert_one({
        "email": email,
        "refresh_token": refresh_token,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z"
    })

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "email": email,
        "role": user_role,
        "workspace_type": user.get("workspace_type", "marketing"),
        "is_verified": user.get("is_verified", True)
    }


@router.post("/refresh")
def refresh_token_endpoint(req: RefreshRequest, db: Database = Depends(get_db)):
    """AUTH-03: Refreshes short-lived access token using valid refresh token."""
    payload = decode_access_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

    email = payload.get("sub")
    db_token = db.refresh_tokens.find_one({"email": email, "refresh_token": req.refresh_token})
    if not db_token:
        raise HTTPException(status_code=401, detail="Revoked refresh token.")

    user = db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists.")

    new_access_token = create_access_token(data={"sub": email, "role": user.get("role", "owner")})
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout")
def logout(req: RefreshRequest, current_user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    """AUTH-03: Revokes refresh token on logout."""
    db.refresh_tokens.delete_many({"email": current_user["email"], "refresh_token": req.refresh_token})
    return {"message": "Successfully logged out and session revoked."}


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Database = Depends(get_db)):
    """AUTH-05: Generates password reset token & dispatches reset email link."""
    email = req.email.lower().strip()
    user = db.users.find_one({"email": email})
    if not user:
        return {"message": "If an account exists with this email, a password reset link has been sent."}

    reset_token = uuid.uuid4().hex + uuid.uuid4().hex
    reset_exp = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

    db.users.update_one(
        {"email": email},
        {"$set": {"reset_token": reset_token, "reset_expires": reset_exp.isoformat() + "Z"}}
    )

    reset_url = f"{FRONTEND_BASE_URL}/reset-password?token={reset_token}"
    email_body = f"Password Reset Request\n\nClick the link below to reset your password (valid for 1 hour):\n{reset_url}\n\nIf you did not request this, ignore this email."
    send_email(email, "Reset Your Aura Account Password", email_body)

    return {
        "message": "If an account exists with this email, a password reset link has been sent.",
        "reset_url": reset_url
    }


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Database = Depends(get_db)):
    """AUTH-05: Verifies reset token and updates password."""
    user = db.users.find_one({"reset_token": req.token})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token.")

    exp_str = user.get("reset_expires")
    if exp_str:
        try:
            exp_dt = datetime.datetime.fromisoformat(str(exp_str).replace("Z", ""))
            if datetime.datetime.utcnow() > exp_dt:
                raise HTTPException(status_code=400, detail="Reset token has expired.")
        except Exception:
            pass

    hashed = get_password_hash(req.new_password)
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"hashed_password": hashed},
            "$unset": {"reset_token": "", "reset_expires": ""}
        }
    )
    # Revoke all existing sessions
    db.refresh_tokens.delete_many({"email": user["email"]})
    return {"message": "Password successfully reset! You can now log in with your new password."}


@router.post("/google")
def google_login(req: GoogleAuthRequest, db: Database = Depends(get_db)):
    if not GOOGLE_OAUTH_CLIENT_ID:
        raise HTTPException(
            status_code=501,
            detail="Google Sign-In isn't configured. Set GOOGLE_OAUTH_CLIENT_ID in .env.",
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
            "workspace_type": "marketing",
            "company_name": idinfo.get("name") or "Aura Business",
            "role": "owner",
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "is_active": True,
            "is_verified": True,
            "tokens": 9999,
            "transactions": [],
        }
        db.users.insert_one(user_doc)

    access_token = create_access_token(data={"sub": email, "role": user.get("role", "owner") if user else "owner"})
    refresh_token = create_refresh_token(data={"sub": email})

    db.refresh_tokens.insert_one({
        "email": email,
        "refresh_token": refresh_token,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z"
    })

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "email": email,
        "role": user.get("role", "owner") if user else "owner",
        "workspace_type": user.get("workspace_type", "marketing") if user else "marketing",
        "is_verified": True
    }


@router.post("/apple")
def apple_login():
    raise HTTPException(
        status_code=501,
        detail="Sign in with Apple requires a paid ($99/yr) Apple Developer account.",
    )


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "email": current_user["email"],
        "tokens": current_user.get("tokens", 0),
        "role": current_user.get("role", "owner"),
        "is_verified": current_user.get("is_verified", True),
        "workspace_type": current_user.get("workspace_type", "marketing"),
        "company_name": current_user.get("company_name", "Aura Business")
    }
