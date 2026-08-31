from typing import Optional
import os
import sys
import secrets
import datetime
from jose import JWTError, jwt
import bcrypt

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# --- SECRET_KEY -------------------------------------------------------
# FIX (security): this file used to hardcode a fallback JWT signing secret
# directly in source (`os.getenv("SECRET_KEY", "b33fa43d...")`). Anyone who
# could read the repo could forge valid tokens for any account. There is no
# safe hardcoded fallback for a signing secret, so: use the real env var if
# set, otherwise generate a random one for this process only, and warn
# loudly. A random per-process secret means restarting the server
# invalidates all existing tokens (acceptable for local dev) and MUST NOT be
# relied on across multiple server instances or in production — set
# SECRET_KEY in your .env for anything beyond local experimentation.
_env_secret = os.getenv("SECRET_KEY")
if _env_secret:
    SECRET_KEY = _env_secret
else:
    SECRET_KEY = secrets.token_hex(32)
    print(
        "WARNING: SECRET_KEY is not set in the environment. Generated a random ephemeral "
        "secret for THIS PROCESS ONLY — all issued tokens will stop validating after a "
        "restart, and this must never be relied on across multiple server instances. "
        "Set SECRET_KEY in your .env before doing anything beyond local testing.",
        file=sys.stderr,
    )


def get_password_hash(password: str) -> str:
    """Hashes a plain password using bcrypt directly (prevents passlib wrap-bug crashes)."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against its hashed value using bcrypt directly."""
    if not hashed_password:
        return False
    try:
        pwd_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception as e:
        print(f"Bcrypt verification error: {e}")
        return False


def create_access_token(data: dict) -> str:
    """Generates a signed JWT access token containing claims data."""
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decodes and validates a signed JWT token claims."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
