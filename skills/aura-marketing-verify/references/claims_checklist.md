# Aura Marketing AI OS — Claims Verification Checklist

Use this checklist when manually reviewing the codebase against the spec doc.

## Verdict Legend
- ✅ **VERIFIED**: Code exists, is wired up, and logic performs what is claimed.
- ⚠️ **PARTIAL**: Code exists but logic is incomplete, fallback-heavy, or partially stubbed.
- ❌ **MISSING**: File, route, or function claimed in spec doc does not exist in repo.
- 🚩 **FAKE**: Code exists but deliberately returns static/hardcoded dummy data or passes verification unconditionally.

---

## A. File & Module Inventory Claims

| ID | Spec Claim | File Path | Checked | Verdict | Reason / Line Ref |
|:---|:---|:---|:---:|:---:|:---|
| A1 | FastAPI Main Entrypoint | `backend/main.py` | [ ] | | |
| A2 | Authentication Helpers & Models | `backend/auth.py`, `backend/deps.py`, `backend/auth_router.py` | [ ] | | |
| A3 | Wallet & Payment Integration Router | `backend/wallet_router.py` | [ ] | | |
| A4 | Marketing Doctor Diagnostics Router | `backend/marketing_doctor.py` | [ ] | | |
| A5 | SEO Engine Opportunities Router | `backend/seo_engine.py` | [ ] | | |
| A6 | Campaign & Attribution Router | `backend/campaigns.py` | [ ] | | |
| A7 | Website Audit Scraper Router | `backend/webaudit_router.py` | [ ] | | |
| A8 | Analytics & Token Usage Router | `backend/analytics_router.py` | [ ] | | |
| A9 | AI Image Editing Multi-Provider Router | `backend/image_router.py` | [ ] | | |
| A10 | Unit & Integration Test Suite | `backend/tests/test_api.py` | [ ] | | |

---

## B. Feature Claims

| ID | Spec Claim | Target Location | Checked | Verdict | Reason / Line Ref |
|:---|:---|:---|:---:|:---:|:---|
| B1 | Top 10 Opportunity Engine | `backend/seo_engine.py` | [ ] | | |
| B2 | Real DOM & SPA Hydration Inspector | `backend/marketing_doctor.py` | [ ] | | |
| B3 | Multi-Touch Attribution Engine (First/Last/Linear/W-Shaped) | `backend/campaigns.py` | [ ] | | |
| B4 | Razorpay HMAC Payment Verification | `backend/wallet_router.py` | [ ] | | |
| B5 | Database Fallback & TTL Indexes | `backend/database.py` | [ ] | | |

---

## C. Architectural Upgrade Claims

| ID | Spec Claim | Target Location | Checked | Verdict | Reason / Line Ref |
|:---|:---|:---|:---:|:---:|:---|
| C1 | Secure JWT Secret Handling (No hardcoded key fallback) | `backend/auth.py` | [ ] | | |
| C2 | Explicit Origin CORS Configuration | `backend/main.py` | [ ] | | |
| C3 | Mandatory Bearer Auth Guard (No demo user fallback) | `backend/deps.py` | [ ] | | |
| C4 | Production Admin Seed Disabled | `backend/main.py` | [ ] | | |

---

## D. Empirical Test & Runtime Claims

| ID | Spec Claim | Test Command / Endpoint | Checked | Verdict | Reason / Line Ref |
|:---|:---|:---|:---:|:---:|:---|
| D1 | Auth Registration & Login Unit Test | `backend/tests/test_api.py` | [ ] | | |
| D2 | Payment Verification Unit Test | `backend/tests/test_api.py` | [ ] | | |
| D3 | Marketing Doctor Scan Unit Test | `backend/tests/test_api.py` | [ ] | | |
| D4 | Attribution Computation Unit Test | `backend/tests/test_api.py` | [ ] | | |
| D5 | Full Unit Test Suite Passing | `python3 -m unittest backend/tests/test_api.py` | [ ] | | |
| D6 | Live Endpoint: `POST /api/auth/register` | `http://localhost:8000/api/auth/register` | [ ] | | |
| D7 | Live Endpoint: `POST /api/wallet/create-razorpay-order` | `http://localhost:8000/api/wallet/create-razorpay-order` | [ ] | | |
| D8 | Live Endpoint: `POST /api/marketing-doctor/diagnose` | `http://localhost:8000/api/marketing-doctor/diagnose` | [ ] | | |
| D9 | Live Endpoint: `GET /api/campaigns/attribution/{id}` | `http://localhost:8000/api/campaigns/attribution/1` | [ ] | | |
