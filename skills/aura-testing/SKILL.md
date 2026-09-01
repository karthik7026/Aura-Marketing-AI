---
name: aura-testing
description: End-to-end functional UI testing skill for Aura Marketing AI Operating System using Playwright Chromium UI automation to test all user flows (Signup, Login, Bento Grid Tabs, SEO Search, Website Audit, Competitor Intel, Wallet Razorpay Checkout, AI Video Studio, Campaign Ad Generator, and Mobile Viewports).
---

# Aura Marketing AI OS — End-to-End Functional UI Testing Skill

This skill provides step-by-step UI automation instructions and Playwright test scripts to perform **100% End-to-End Blackbox Functional UI Testing** on the live Netlify production app (**`https://auradigimarketing.netlify.app/`**).

---

## 🎯 Target Production URL
- **Frontend App**: `https://auradigimarketing.netlify.app/`
- **Automation Engine**: Playwright Chromium (Viewport: 1280x800 Desktop & 390x844 Mobile)

---

## 🎭 End-to-End Functional User Flows

### Flow 1: User Onboarding & Registration (`/signup`)
1. Open browser and navigate to `https://auradigimarketing.netlify.app/signup`.
2. Fill input fields:
   - Email: `end2end_user@aura.com`
   - Password: `Password123!`
   - Company Name: `Acme Growth Studio`
3. Click **Create Account** button.
4. Verify form validation loading spinner and success message popup.

---

### Flow 2: Authentication & Login (`/login`)
1. Navigate to `https://auradigimarketing.netlify.app/login`.
2. Enter registered credentials into email and password inputs.
3. Click **Log In** button.
4. Verify session token creation and automatic redirect to `/marketing`.

---

### Flow 3: Marketing Dashboard & Sidebar Navigation (`/marketing`)
1. Navigate to `https://auradigimarketing.netlify.app/marketing`.
2. Verify top bar displays **Marketing Health Score 78/100** and user profile details.
3. Sequentially click all sidebar navigation tabs:
   - 📊 **Overview Tab**: Bento grid cards, campaign score summary.
   - 🔍 **SEO & Rankings Tab**: Search input, Autocomplete suggestions.
   - ⚡ **Website Audit Tab**: Live scan URL input form.
   - 🕵️ **Competitor Intel Tab**: Competitor URL input & tech stack chips.
   - 📈 **Marketing Analytics Tab**: Usage charts & activity feed.
   - 🔔 **Notifications Tab**: Unread count badge & notifications list.

---

### Flow 4: Interactive SEO & Google Trends Search
1. Open **SEO & Rankings** tab in `/marketing`.
2. Type keyword (`"ai marketing"`) into the search bar.
3. Assert Google Autocomplete suggestions dropdown appears.
4. Click **Search Trends**.
5. Assert Google Trends interest timeline chart & difficulty score card render on screen.

---

### Flow 5: Interactive Website Audit & Core Web Vitals
1. Open **Website Audit** tab.
2. Enter target domain URL (`https://google.com`) into audit input.
3. Click **Run Audit**.
4. Observe loading progress indicator.
5. Assert 4 color-coded Lighthouse score dials (Performance, SEO, A11y, Best Practices) and Core Web Vitals cards render.

---

### Flow 6: Interactive Competitor Intel Scraping
1. Open **Competitor Intel** tab.
2. Enter competitor domain into input field.
3. Click **Analyze Competitor**.
4. Assert scraped title, meta description, tech stack badges, and 4 SWOT analysis cards populate the UI.

---

### Flow 7: Wallet Token Top-Up & Razorpay Checkout (`/wallet`)
1. Navigate to `https://auradigimarketing.netlify.app/wallet`.
2. Verify 3 token package cards (*Starter*, *Pro Marketer*, *Enterprise*).
3. Click **Purchase Pro Plan** (₹29, 250 tokens).
4. Assert Razorpay checkout modal mounts on screen with test key `rzp_test_TVFsRcrLVPCbPu`.

---

### Flow 8: AI Video Studio Prompt & GPU Stream (`/dashboard`)
1. Navigate to `https://auradigimarketing.netlify.app/dashboard`.
2. Enter video prompt into textarea: `"Futuristic cyberpunk neon marketing campaign in 8k"`.
3. Click **Generate AI Video**.
4. Observe live compilation log stream and verify HTML5 video player controls.

---

### Flow 9: Campaign Manager & Multi-Channel Ad Copy
1. Open **Campaign Manager** tab.
2. Enter product name and target audience.
3. Click **Generate Ad Copy**.
4. Assert multi-channel ad previews (Google Ads headline, Meta Ads primary text, LinkedIn banner) render on screen.

---

### Flow 10: Responsive Mobile Viewport Verification (`390x844`)
1. Set browser viewport to `390x844` (Pixel 9 / iPhone mobile view).
2. Navigate to `https://auradigimarketing.netlify.app/marketing`.
3. Assert mobile hamburger menu toggles correctly and UI cards stack vertically without overflow.

---

## 🛠️ Automated Playwright Functional UI Command

To execute all 10 Functional UI User Flows in Chromium and save screenshots:

```bash
python3 /tmp/manual_blackbox_test.py
```
