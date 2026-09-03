---
name: aura-marketing-verify
description: Audits the "Aura Marketing AI OS" codebase (Next.js/FastAPI/MongoDB/Razorpay marketing platform) against its own architecture/review spec doc, verifying every claimed feature, test, and upgrade line-by-line against real code and live behavior rather than trusting the doc's text. Implements anything found missing, stubbed, or faked, then re-verifies. Use this whenever the user asks to check, audit, verify, or "test" whether things described in the Aura Marketing spec doc (Top 10 Opportunity Engine, AI Marketing Doctor, SPA hydration inspector, touchpoint attribution engine, Razorpay wallet, Mongo indexes/TTL, the 5-test suite, or the live endpoint checks) are actually implemented, or asks to bring the codebase up to what the doc claims. Also use for general "does this spec match the code" audits of this specific project, even if phrased as "review my code" or "run the tests and tell me what's broken."
---

# Aura Marketing AI OS — Spec-vs-Reality Verification

## Why this skill exists

The project has a polished-looking spec document ("AURA MARKETING AI OPERATING SYSTEM... Status: All High-Leverage Upgrades Implemented & Verified") that makes specific, checkable claims: file names, function behavior, a 5-test unit suite with an exact runtime ("Ran 5 tests in 0.842s"), and 4 live endpoint checks.

**Treat every claim in that doc as unverified until you personally confirm it against the real repo.** Confident formatting, checkmarks, "Status: Verified" banners, and specific-sounding numbers (test counts, timings, ratings out of 10) are not evidence — they're exactly what a doc would look like whether or not the underlying code exists. Your job is to independently re-derive the truth, not to summarize the doc's claims back as fact.

The full claim-by-claim checklist lives in `references/claims_checklist.md` — read it before starting. It has ~30 individual falsifiable items grouped into: file inventory, feature claims, architectural upgrade claims, and empirical test/runtime claims, plus a section of common red flags to actively hunt for (fake tests, mocked-out assertions, hardcoded responses).

## Workflow

### 1. Locate the repo
Find the actual project on disk (ask the user for the path if it's not obvious, or check the current working directory / recently opened folder). Do not proceed on the spec doc's text alone — if you can't find real files, say so plainly instead of grading the doc.

### 2. Run the automated pre-check
```bash
python3 scripts/verify_checklist.py --repo /path/to/repo
```
Optionally add `--base-url http://localhost:8000` if the FastAPI server is already running, to hit live endpoints.

This script only does the mechanical parts: confirms which files from the inventory actually exist, greps for specific markers (route strings, field names, index calls), runs the existing test suite for real, and scans for common red-flag patterns (bare `except: pass`, mocked assertions, `TODO`/stub comments, `return True` verifiers).

**A grep hit is a lead, not a verdict.** If `verify_checklist.py` reports `C4_w_shaped: true`, that only means the string "w-shaped" or "w_shaped" appears somewhere in `campaigns.py` — go read that code and confirm the math actually produces four distinct attribution numbers, not the same value four times, before marking it verified.

### 3. Manually verify every item in `references/claims_checklist.md`
Go row by row. For each one:
- Read the actual implementation (not just search for it).
- For the test suite (section D): re-run `python3 -m unittest backend/tests/test_api.py` yourself and paste your own fresh output. Never reuse the doc's reported "Ran 5 tests in 0.842s -> OK!" — that's not something you can verify by reading, only by running.
- For the payment signature test in particular: also try mutating the signature/payload and re-running, to confirm the test can actually fail. A verification function that returns `True` unconditionally is a serious bug to flag, not a passing test.
- For live endpoints (section D7–D10): actually boot the server and `curl` them yourself. Don't accept "200 OK" claims without a fresh request/response you generated in this session.
- Assign each item one of: ✅ VERIFIED / ⚠️ PARTIAL / ❌ MISSING / 🚩 FAKE, as defined in the checklist file.

### 4. Implement anything that's ❌ MISSING or 🚩 FAKE
For each gap found:
- Build the real thing — don't patch the doc to match reality, patch the code to match the actual intended feature.
- Prioritize by risk: payment signature verification (wallet_router.py) and the attribution math (campaigns.py) matter more than cosmetic gaps like styling.
- Use the relevant skill for any deliverable file types encountered (e.g. if asked to also regenerate a spec/report document, check for a docx/pdf/pptx skill; this skill only covers the code audit + implementation).
- After implementing, re-run `verify_checklist.py` and re-check the specific row manually — don't just assume your fix worked.

### 5. Produce the final report
Give the user a table (one row per checklist item, using the same IDs as `references/claims_checklist.md`) with the verdict and a one-line reason ("read campaigns.py:142 — linear and w-shaped both divide by touchpoint count without weighting, same result" is a real reason; "looks fine" is not). Then list what you implemented/fixed and how you confirmed it works now. End with an honest overall verdict — it's fine and expected for this to land somewhere between "half of this was real" and "fully verified now," rather than confirming the doc's own "Status: All Upgrades Implemented & Verified" framing by default.

## Ground rules

- Never mark something ✅ based on the spec doc's own prose, comments, docstrings, or naming — only based on logic you read or behavior you observed.
- If the repo can't be found or a claim can't be checked (e.g. no Mongo instance running), say exactly that — don't guess a verdict to fill the table.
- If you find something worse than "missing" — e.g., a payment verification path that's actively insecure — call it out clearly and prioritize fixing it, don't bury it as one row among many.
- Keep the user's trust in mind: the whole point of this skill is to be the check the spec doc's own "Status: Verified" line was supposed to be but wasn't demonstrated to be.
