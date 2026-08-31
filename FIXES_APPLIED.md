# Fixes Applied — Aura Marketing AI Operating System

This document summarizes the fixes applied to your codebase in response to the issues identified in `Aura_Marketing_AI_Review.md` and `Aura_Marketing_AI_OS_BRD.docx`. Scope was constrained to **free-tier / no-cost APIs only**, per your instruction ("use free API's, this is just for my learning purpose").

Every changed file has a `FIX:` or `NOTE:` comment at the relevant line pointing back to the review/BRD, so you can trace exactly why each change was made while you're learning the codebase.

All logic was written and unit-tested in an isolated sandbox (15 passing tests, see `backend/tests/test_api.py`) *before* being copied onto your machine, and every file was then verified **byte-for-byte identical** (SHA-256 hash match) between the tested version and the deployed version — so what was tested is exactly what's now running.

---

## 1. Security fixes (closed silently-broken or dangerous behavior)

| Issue | File | Fix |
|---|---|---|
| Hardcoded JWT `SECRET_KEY` fallback | `backend/auth.py` | Now uses `SECRET_KEY` env var if set; otherwise generates a random per-process secret and warns loudly on startup instead of using a fixed, guessable default. |
| Every endpoint silently fell back to a hardcoded `demo.user@aura.com` (9999 tokens) when no auth header was sent | `backend/deps.py` (new), all routers | New shared `get_current_user()` dependency now returns **401** with no/invalid token. No anonymous fallback anywhere. |
| Payment verification "fail-open": missing `RAZORPAY_KEY_SECRET` silently approved any payment | `backend/wallet_router.py` | Now returns **500/400** for any non-mock order when Razorpay isn't configured, instead of minting free tokens. Mock orders (`order_mock_*`, used only when Razorpay is fully unconfigured) still work for local dev. |
| No idempotency check on payments — replaying a payment payload could double-credit tokens | `backend/wallet_router.py` | Scans the user's transaction history for the `razorpay_payment_id` before crediting; returns the prior result if already processed. |
| CORS wide open (`allow_origins=["*"]` + credentials) | `backend/main.py` | Now reads `ALLOWED_ORIGINS` env var (comma-separated), defaults to `localhost:3000` only. |
| Admin account auto-seeded unconditionally on every boot | `backend/main.py` | Now gated behind `SEED_DEMO_ADMIN=true` (default `false`). |

## 2. Fabricated data → real data (or an honest label when it can't be real)

| Feature | File | What changed |
|---|---|---|
| SEO rank/volume numbers | `backend/seo_engine.py`, `backend/serp.py` (new) | Real Google Custom Search API rank checks + Google Trends interest proxy when `GOOGLE_CSE_API_KEY`/`GOOGLE_CSE_CX` are set. Falls back to labeled sample data otherwise — every item now carries a `data_source` field. |
| Website audit scores (Lighthouse-style) | `backend/webaudit_router.py` | Real Google PageSpeed Insights scores (works even without an API key, at lower quota). Falls back to a heuristic, explicitly labeled `heuristic_estimate_pagespeed_unavailable`. |
| Competitor tech-stack detection | `backend/webaudit_router.py` | Was a hardcoded list; now detected from real scraped page signals (Next.js, React, Vue, Cloudflare, GA4, Tailwind). |
| Marketing Doctor scores (content/social/ads/AI-search) | `backend/marketing_doctor.py` | SEO + conversion scores were already real (live DOM inspection) and are unchanged. The 4 heuristic-only scores now carry a `score_disclosure` map so the UI *can* show which numbers are measured vs. estimated. |
| Analytics dashboard "daily token usage" | `backend/analytics_router.py` | Was a static fake 7-day array; now aggregated from the user's real transaction history. |
| Notifications feed | `backend/analytics_router.py` | Was a fixed fake feed; now derived from the user's real last-10 transactions. |
| Campaign metrics on creation | `backend/campaigns.py` | Was fabricated (14,200 impressions, etc.) from the moment a campaign was created; now starts at zero with `metrics_data_source: "not_connected_no_real_ad_platform"` — honest, since no ad platform is actually connected. |
| Fallback "demo" campaign in the campaign list | `backend/campaigns.py` | Removed entirely; list is now always the real (possibly empty) result. |
| Attribution report with no data | `backend/campaigns.py` | Was fabricated demo numbers; now an honest empty response. The actual multi-touch attribution math (first/last/linear/W-shaped) was already correctly implemented and is unchanged. |

## 3. AI-generated content (Groq, free tier)

`backend/llm.py` (new) calls Groq's free OpenAI-compatible API. Every endpoint below tries the LLM first and falls back to the original static template if it's unavailable — and always discloses which one it used via a `generation_source: "llm" | "template"` field:

- `POST /api/seo/why-not-top10`, `/generate-fix-plan`, `/keyword-clustering`
- `POST /api/campaigns/ads/generate-creatives`, `/social/calendar`, `/email/generate-sequence`

**To enable:** get a free key at [console.groq.com](https://console.groq.com/keys) and set `GROQ_API_KEY` in `.env`.

## 4. Previously broken/fake features now actually work

| Feature | File | Fix |
|---|---|---|
| `/api/video/generate` returned 404 — the frontend called it but it was never mounted | `backend/video_router.py` (new) | Now a real route wired to the video generator, with correct token deduction and a `disclosure` field explaining exactly which tier produced the result (Replicate / your private GPU / a free Hugging Face Space / your local library / a stock clip) — see section 8 below for the free video generation system added on top of this. |
| AI image tools (`upscale`, `enhance`, `remove-bg`, etc.) charged tokens but returned the *original, unedited* image | `backend/image_router.py` | `upscale`/`enhance`/`remove-bg` now do real local processing (Pillow/rembg — free, no API key) and only charge tokens on success. Tools needing a paid provider we don't have (cleanup, reimagine, search-replace, outpaint, style-transfer) now return **501** *before* charging, instead of silently no-op'ing and charging anyway. |
| Generated email sequences had no way to actually reach anyone | `backend/campaigns.py`, `backend/email_service.py` (new) | New `POST /api/campaigns/email/send-sequence` actually sends via Resend's free tier (3,000 emails/month, no card) when `RESEND_API_KEY` is set. |
| Frontend called wrong wallet endpoint names | `src/app/marketing/page.tsx` (lines ~1738, ~1787) | `/api/wallet/order` → `/api/wallet/create-razorpay-order`; `/api/wallet/verify` → `/api/wallet/verify-payment` (these never matched the actual backend routes). |
| Google Sign-In | `backend/auth_router.py` | New `POST /api/auth/google`, verifies a real Google ID token via `google-auth` (free). Returns 501 with setup instructions if `GOOGLE_OAUTH_CLIENT_ID` isn't set. |
| Apple Sign-In | `backend/auth_router.py` | New `POST /api/auth/apple` returns an honest **501** explaining this needs a paid ($99/yr) Apple Developer account — explicitly out of scope for a free-API build, rather than being silently missing. |

## 5. Free API keys you can add to unlock full functionality

Your `.env` file now has placeholders (with signup links) for all of these. Everything works with **zero** of them configured — you just get honest fallback/template behavior instead of real data:

| Variable | Free tier | Get it at |
|---|---|---|
| `GROQ_API_KEY` | Generous free tier | console.groq.com/keys |
| `GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_CX` | 100 queries/day | console.cloud.google.com + programmablesearchengine.google.com |
| `PAGESPEED_API_KEY` | Optional (works without it) | console.cloud.google.com |
| `GOOGLE_OAUTH_CLIENT_ID` | Free | console.cloud.google.com/apis/credentials |
| `RESEND_API_KEY` | 3,000 emails/month | resend.com |
| `SECRET_KEY` | — | any random 32+ char string |
| `PRIVATE_GPU_ENDPOINT` | Your own Colab/Kaggle GPU time | `notebooks/free_video_gpu.ipynb`, Part B |
| `HF_VIDEO_SPACE` / `HF_TOKEN` | Free (public queue) | already defaults to `Wan-AI/Wan2.1`; token from huggingface.co/settings/tokens |

## 6. Free video generation — three combined tiers, all $0

`/api/video/generate` previously only had two states: a genuine Replicate render (paid) or a generic Mixkit stock clip pretending to be "AI compiled." Three free tiers now sit between those, tried in this order, each falling through honestly to the next rather than hanging or faking a result:

| Tier | How | Config | Reality check |
|---|---|---|---|
| **1. Your own Colab/Kaggle GPU** | `backend/generator.py` calls a temporary Gradio link from your own notebook session via `gradio_client` | Run `notebooks/free_video_gpu.ipynb` (Part B) on Kaggle or Colab, paste the printed `https://....gradio.live` link into `PRIVATE_GPU_ENDPOINT` in `.env` | Real generation, your own dedicated GPU (Kaggle: 30 free GPU-hrs/week, T4 16GB — no shared queue). It's a temporary link tied to a live session, not an always-on server; when the session ends, calls fail fast and fall through automatically. |
| **2. Public Hugging Face Space** | Same `gradio_client` mechanism, pointed at a public Space | `HF_VIDEO_SPACE` (defaults to `Wan-AI/Wan2.1`), optional `HF_TOKEN` for better queue priority | Genuinely free, no signup required — but shared with everyone on the internet. Tested live against the default Space during development: its queue showed roughly 107 hours of backlog for anonymous callers, so expect this tier to often time out and fall through to tier 3/4 unless you add a token or point it at a less crowded Space. |
| **3. Local generated-clip library** | `backend/generated_library/manifest.json` — a real AI-generated clip is served back through `/api/video/library/{filename}` when its tags match the prompt | Run `notebooks/free_video_gpu.ipynb` (Part A) to batch-generate one clip per category and drop the output in `backend/generated_library/` | Not live, but a genuine AI render (not stock footage) restocked whenever you feel like running the notebook. Empty by default — falls through to tier 4 until you fill it. |
| **4. Generic stock clip** (unchanged) | `SANDBOX_FEEDS` in `backend/generator.py` | none | The original honest fallback — labeled as such, never claims to be AI-generated. |

**Why not just run Colab/Kaggle as an always-on API?** I deliberately did not build that. Turning a free notebook into a permanent server means tunnelling it (ngrok, etc.) into a public endpoint your backend hits anytime — and Google's Colab free-tier terms explicitly prohibit exactly that pattern ("bypassing the notebook interface to interact mainly through another web interface"), risking your account, not just the session. Tier 1 above uses Gradio's own official `share=True` temporary-link feature instead — the standard, sanctioned way people demo a live Colab/Kaggle session — and it's inherently session-bound rather than persistent, which is an honest limit of the free-tier landscape, not something any workaround removes.

Every generation response now includes a `generation_source` field (`replicate` / `private_gpu` / `huggingface_space` / `video_library` / `sandbox`) alongside the existing `disclosure` text, so the frontend (or you, while testing) always knows exactly which tier produced a given clip.

## 7. Explicitly out of scope for this pass

- **Chat / interview / meetings UI** — the review flagged these as dead frontend UI with no backing endpoints. Fixing this safely requires a full read of the 5,685-line `marketing/page.tsx` file to avoid breaking unrelated code; not attempted here to keep this pass focused and low-risk.
- **Real ad publishing to Google/Meta/LinkedIn** — needs live ad accounts + platform app review on each network; not achievable with a free API key alone. Campaign metrics remain honestly at zero until this is built.
- **On-device automated test run** — this machine's shell has no network access to install Python packages (pip → pypi.org is blocked by the network allowlist), so the full test suite couldn't be re-run directly on your computer. It was fully run and passed (15/15) in the sandbox before transfer, and every file was verified byte-identical afterward, but you may want to `pip install -r backend/requirements.txt` and run `python -m unittest backend/tests/test_api.py` yourself once to see it green on your own machine.

## 8. How to verify this yourself

```bash
cd "AI agent"
pip install -r backend/requirements.txt --break-system-packages
python -m unittest backend.tests.test_api -v
```

You should see 15 tests pass, including ones that specifically assert the old bugs are fixed (e.g. `test_unauthenticated_requests_are_rejected`, `test_payment_idempotency_does_not_double_credit`, `test_image_edit_upscale_actually_transforms_and_charges_correctly`) and that the new free video tiers fall back honestly instead of hanging (`test_video_generation_prefers_private_gpu_then_falls_back_honestly`, `test_video_generation_falls_back_honestly_when_hf_space_unavailable`, `test_video_generation_prefers_local_library_clip_over_generic_stock`).
