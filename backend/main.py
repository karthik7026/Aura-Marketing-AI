import os
import datetime
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Local imports
from backend.database import get_db, init_db_indexes
from backend.auth import get_password_hash

# Domain Routers
from backend.auth_router import router as auth_router
from backend.wallet_router import router as wallet_router
from backend.image_router import router as image_router
from backend.webaudit_router import router as webaudit_router
from backend.analytics_router import router as analytics_router
from backend.marketing_doctor import router as marketing_doctor_router
from backend.seo_engine import router as seo_engine_router
from backend.campaigns import router as campaigns_router
from backend.video_router import router as video_router  # FIX: was built (generator.py) but never mounted

app = FastAPI(
    title="Aura Marketing AI Operating System API",
    description="Thin orchestrator backend mounting Auth, Wallet, AI Image, Web Audit, Analytics, Marketing Doctor, SEO Engine, Campaigns, and Video routers.",
    version="2.2.0"
)

# --- CORS ---------------------------------------------------------------
# FIX (security): this used to be allow_origins=["*"] together with
# allow_credentials=True — an invalid/unsafe combination most browsers
# reject outright, and a sign this was never tested against a real deployed
# frontend origin. Now reads an explicit allowlist from ALLOWED_ORIGINS
# (comma-separated) with a sane localhost default for dev.
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Domain Routers
app.include_router(auth_router)
app.include_router(wallet_router)
app.include_router(image_router)
app.include_router(webaudit_router)
app.include_router(analytics_router)
app.include_router(marketing_doctor_router)
app.include_router(seo_engine_router)
app.include_router(campaigns_router)
app.include_router(video_router)


@app.on_event("startup")
def startup_event():
    db = next(get_db())
    init_db_indexes(db)

    # FIX (security): a default admin@aura.com / admin123 account used to be
    # auto-seeded on every startup, unconditionally. That's a real backdoor
    # if this ever runs somewhere reachable. Now opt-in only, for local dev,
    # via SEED_DEMO_ADMIN=true in .env — off by default.
    if os.getenv("SEED_DEMO_ADMIN", "false").lower() == "true":
        admin_email = "admin@aura.com"
        existing = db.users.find_one({"email": admin_email})
        if not existing:
            hashed = get_password_hash("admin123")
            admin_user = {
                "email": admin_email,
                "hashed_password": hashed,
                "provider": "local",
                "provider_id": None,
                "created_at": datetime.datetime.utcnow().isoformat() + "Z",
                "is_active": True,
                "tokens": 9999,
                "transactions": []
            }
            db.users.insert_one(admin_user)
            print("DEV MODE: Seeded admin@aura.com / admin123 because SEED_DEMO_ADMIN=true. "
                  "Do NOT set this in any deployed environment.")


@app.get("/")
def root_status():
    return {
        "status": "online",
        "system": "Aura Marketing AI Operating System API",
        "version": "2.2.0",
        "documentation": "/docs"
    }
