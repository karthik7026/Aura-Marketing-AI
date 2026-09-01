---
name: aura-testing
description: Comprehensive end-to-end testing skill for Aura Marketing AI Operating System covering all functional BRD scenarios (Auth, Razorpay Payments, Marketing Doctor, SEO Engine, AI Video Studio, Campaign Ads, Attribution, and Netlify/Render deployment verification).
---

# Aura Marketing AI OS — End-to-End QA Testing Skill

This skill provides step-by-step instructions and automated test scripts to verify 100% of the functional scenarios defined in the **Aura Marketing AI OS Business Requirements Document (`Aura_Marketing_AI_OS_BRD.docx`)**.

---

## 🎯 Target Environments

- **Local Dev Server**: 
  - Frontend: `http://localhost:3000`
  - Backend: `http://127.0.0.1:8000`
- **Live Netlify Production**: 
  - Frontend: `https://auradigimarketing.netlify.app/`
  - Backend: `https://aura-marketing-backend.onrender.com`

---

## 🧪 Test Scenarios Execution Guide

### Scenario 1: Authentication & User Session Management (`AUTH-01 to 07`)

1. **User Registration (`POST /api/auth/register`)**:
   - Register a unique email (`testuser_<uuid>@aura.com`) with a password.
   - Assert response returns `200 OK` and a valid JWT `access_token`.

2. **User Login (`POST /api/auth/login`)**:
   - Authenticate with registered credentials.
   - Verify JWT payload contains `email` and `sub`.

3. **Session User Profile (`GET /api/auth/me`)**:
   - Call `/api/auth/me` with `Authorization: Bearer <token>`.
   - Verify 401 redirect when an invalid token is supplied.

---

### Scenario 2: Wallet & Razorpay Payment Verification (`PAY-01 to 04`)

1. **Create Razorpay Order (`POST /api/wallet/create-razorpay-order`)**:
   - Request order creation for Pro Marketer Plan (₹29, 250 tokens).
   - Assert response contains `order_id`, `amount` (in paisa), and `key_id` (`rzp_test_TVFsRcrLVPCbPu`).

2. **HMAC Signature Verification & Token Credit (`POST /api/wallet/verify-payment`)**:
   - Verify payment signature verification.
   - Assert account token balance increases by `+250 tokens`.
   - Assert idempotency: sending the same `order_id` twice returns `Payment already verified` without double-crediting.

---

### Scenario 3: Marketing Doctor Site Scan & Framework Detection (`AUDIT-01 to 03`)

1. **Live Site Scan (`POST /api/marketing-doctor/diagnose`)**:
   - Execute audit against target domain (e.g., `https://google.com`).
   - Verify real DOM signals (title, meta description, H1, JSON-LD Schema).
   - Assert SPA framework detection (Next.js / Vue / Nuxt).

---

### Scenario 4: SEO Top 10 Opportunities & Rank Checking (`SEO-01 to 03`)

1. **Google Autocomplete Suggestions (`GET /api/seo/suggest?q=marketing`)**:
   - Verify real-time Google search suggestions are returned.

2. **Google Trends & SERP Difficulty (`GET /api/seo/trends?keyword=ai`)**:
   - Assert interest over time data and difficulty scores are populated.

3. **Top 10 Keyword Opportunities (`POST /api/seo/top10-opportunities`)**:
   - Sourced from SerpApi integration.
   - Assert Page-2 ranking keywords and traffic estimates are returned.

---

### Scenario 5: Campaign Manager & Multi-Channel Ad Copy (`CAMP-01 to 07`)

1. **Generate Ad Creatives (`POST /api/campaigns/ads/generate-creatives`)**:
   - Input product name and target audience.
   - Sourced from Groq LLM (`llama-3.3-70b-versatile`).
   - Assert headlines, primary text, and CTA buttons are generated.

2. **Generate Social Calendar (`POST /api/campaigns/social/generate-calendar`)**:
   - Generate 7-day social post schedule with hashtags.

3. **Generate Email Sequence (`POST /api/campaigns/email/generate-sequence`)**:
   - Generate multi-step welcome/promo email sequence.
   - Sourced from Resend email delivery API.

---

### Scenario 6: AI Video Studio Prompt-to-Video (`STU-01 to 03`)

1. **Submit Video Prompt (`POST /api/video/generate`)**:
   - Submit prompt: `"Futuristic neon cyberpunk marketing campaign in 8k"`.
   - Assert `job_id` is generated and status polling returns `completed`.

---

### Scenario 7: Multi-Touch Attribution Engine (`ANLY-01 to 04`)

1. **Attribution Model Computation (`GET /api/campaigns/attribution/{campaign_id}`)**:
   - Compute First-Touch, Last-Touch, Linear, and W-Shaped attribution over touchpoints.

---

### Scenario 8: Netlify & Render Cloud Deployment Verification (`NFR-SEC / NFR-DATA`)

1. **Netlify Build Verification**:
   - Assert `netlify.toml` uses Node 20 and `@netlify/plugin-nextjs`.
   - Assert `https://auradigimarketing.netlify.app/` returns `200 OK`.

2. **Render Cloud API Verification**:
   - Assert `python3 run_server.py` binds to `0.0.0.0:$PORT`.
   - Assert CORS allows Netlify production origin.

---

## 🛠️ Quick Execution Command

Run the automated test runner in terminal:

```bash
python3 backend/tests/test_api.py
```

Or execute the Playwright browser suite:

```bash
python3 -c "import os; os.system('python3 /tmp/manual_blackbox_test.py')"
```
