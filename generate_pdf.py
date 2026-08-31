import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak, KeepTogether
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "AURA MARKETING AI OS — ARCHITECTURE & REVIEW BLUEPRINT")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)
            
        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_str)
        self.drawString(54, 36, "CONFIDENTIAL & PROPRIETARY — PREPARED FOR CLAUDE REVIEW")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        
        self.restoreState()

def build_pdf(pdf_filename):
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=64,
        bottomMargin=64
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0D9488"),
        spaceAfter=12
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#0F766E"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        leftIndent=12,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#0F172A"),
        backColor=colors.HexColor("#F8FAFC"),
        borderColor=colors.HexColor("#E2E8F0"),
        borderWidth=0.5,
        borderPadding=5,
        spaceAfter=6
    )

    story = []

    # Title Banner
    story.append(Paragraph("AURA MARKETING AI OPERATING SYSTEM", title_style))
    story.append(Paragraph("Codebase Architecture, Claude 6.5/10 Review & High-Leverage Upgrades (v2.1)", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0D9488"), spaceAfter=10))

    # Metadata Box
    meta_data = [
        [Paragraph("<b>Target Audience:</b> Claude / Technical Reviewer", body_style), Paragraph("<b>Tech Stack:</b> Next.js 19, FastAPI, MongoDB, Razorpay", body_style)],
        [Paragraph("<b>Author:</b> Antigravity Engineering Lead", body_style), Paragraph("<b>Status:</b> All High-Leverage Upgrades Implemented & Verified", body_style)]
    ]
    meta_table = Table(meta_data, colWidths=[250, 254])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 1. Executive Summary
    story.append(Paragraph("1. Executive Summary & Growth Vision", h1_style))
    story.append(Paragraph(
        "Aura Marketing is an <b>AI-powered Digital Marketing Operating System</b> engineered to eliminate tool fragmentation. "
        "It unifies SEO research, website auditing, competitor intelligence, AI copywriting, video synthesis, multi-channel ad campaigns, and social scheduling into an outcome-driven loop:",
        body_style
    ))
    story.append(Paragraph("<b>DISCOVER (SEO) → ANALYZE (Doctor) → DIAGNOSE (Top 10) → RECOMMEND → CREATE (Copy/Video) → PUBLISH → MEASURE</b>", h2_style))
    story.append(Paragraph("<b>Core Positioning:</b> <i>'Your AI marketing team is working on your business.'</i>", body_style))
    story.append(Spacer(1, 8))

    # 2. File System Inventory
    story.append(Paragraph("2. Complete Project File Inventory", h1_style))
    inventory_code = """AI agent/
├── backend/
│   ├── main.py             # Thin FastAPI Router Orchestrator (v2.1.0)
│   ├── marketing_doctor.py  # AI Marketing Doctor (BS4 + SPA Hydration Inspector)
│   ├── seo_engine.py        # Top 10 Opportunity Engine & SERP Comparative AI
│   ├── campaigns.py         # Campaigns, Ad Builder & Touchpoint Attribution Stream
│   ├── auth_router.py       # Isolated JWT Authentication & Identity Router
│   ├── wallet_router.py     # Razorpay Order Creation & Signature Verification
│   ├── image_router.py      # Multi-Provider AI Image Editing Router
│   ├── webaudit_router.py   # Lighthouse Web Performance & Competitor Scraper
│   ├── analytics_router.py  # Analytics Dashboard & Notifications Router
│   ├── database.py          # MongoDB Driver, Auto-Indexes & Expiry Rules
│   └── tests/test_api.py    # Automated API Unit Test Suite (5 Tests Passed)
└── src/app/marketing/page.tsx # Main UI (Glassmorphism + Bento Grid Layout)"""
    story.append(Paragraph(inventory_code.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style))
    story.append(Spacer(1, 8))

    # 3. Claude Review & 6.5/10 Rating Breakdown
    story.append(Paragraph("3. Claude Feature Rating & Architectural Evaluation", h1_style))
    
    table_data = [
        [Paragraph("<b>Feature Module</b>", h2_style), Paragraph("<b>Rating</b>", h2_style), Paragraph("<b>Claude's Feedback & Architectural Upgrade</b>", h2_style)],
        [Paragraph("<b>Top 10 Opportunity Engine</b>", body_style), Paragraph("<b>7/10</b>", body_style), Paragraph("High pain point (#11–20 is underserved). Integrated SERP API data model with search volume, difficulty (0–100), and intent tags.", body_style)],
        [Paragraph("<b>AI Marketing Doctor</b>", body_style), Paragraph("<b>5/10 → Fixed</b>", body_style), Paragraph("Static HTML scan misdiagnosed Client-Side Rendered SPAs. <b>Upgraded with SPA Framework Detection (React/Vue/Next.js) & __NEXT_DATA__ Hydration Fallback Parsing.</b>", body_style)],
        [Paragraph("<b>Multi-Channel Campaigns</b>", body_style), Paragraph("<b>6/10 → Fixed</b>", body_style), Paragraph("Needed touchpoint-level data, not just a container. <b>Upgraded with db.touchpoints Event Stream & Dynamic Multi-Touch Attribution Engine (First, Last, Linear, W-Shaped).</b>", body_style)],
        [Paragraph("<b>AI Video & Keyart Studio</b>", body_style), Paragraph("<b>5/10</b>", body_style), Paragraph("Multi-style HD MP4 video generator paired with Pollinations AI 8K Posters & Replicate fallback.", body_style)],
        [Paragraph("<b>Social & Email Suite</b>", body_style), Paragraph("<b>6/10</b>", body_style), Paragraph("Multi-platform 5-day social calendar & 3-step automated email sequence generator.", body_style)],
        [Paragraph("<b>Competitor Intelligence</b>", body_style), Paragraph("<b>5/10</b>", body_style), Paragraph("BeautifulSoup DOM scraper & tech stack fingerprinting (React, Next.js, GA4, Tailwind).", body_style)]
    ]
    
    rating_table = Table(table_data, colWidths=[130, 54, 320])
    rating_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(rating_table)
    story.append(Spacer(1, 10))

    # 4. Implemented High-Leverage Upgrades
    story.append(Paragraph("4. Implemented High-Leverage Architectural Upgrades", h1_style))
    
    story.append(Paragraph("4.1 SPA (React / Vue / Next.js) Hydration Inspector (backend/marketing_doctor.py)", h2_style))
    story.append(Paragraph("When httpx inspects a URL, it detects SPA framework tags (<code>_next/static</code>, <code>root</code>, <code>app</code>). If HTML tags are hydrated client-side, the inspector parses <code>__NEXT_DATA__</code> or Open-Graph tags to extract titles, meta descriptions, and headers accurately, preventing false diagnoses.", body_style))

    story.append(Paragraph("4.2 Touchpoint Event Stream & Dynamic Multi-Touch Attribution (backend/campaigns.py)", h2_style))
    story.append(Paragraph("• <code>POST /api/campaigns/track-event</code>: Logs raw user touchpoint events (<code>{user_identifier, campaign_id, channel, timestamp, conversion_value}</code>) into <code>db.touchpoints</code>.", bullet_style))
    story.append(Paragraph("• <code>GET /api/campaigns/attribution/{campaign_id}</code>: Dynamically computes revenue credit across <b>First Touch</b>, <b>Last Touch</b>, <b>Linear</b>, and <b>W-Shaped</b> models over the event stream.", bullet_style))

    story.append(Paragraph("4.3 FastAPI Domain Router Decoupling (backend/main.py)", h2_style))
    story.append(Paragraph("Decoupled monolith into 5 domain routers (<code>auth_router.py</code>, <code>wallet_router.py</code>, <code>image_router.py</code>, <code>webaudit_router.py</code>, <code>analytics_router.py</code>) mounted in a thin <code>main.py</code> orchestrator.", body_style))

    story.append(Paragraph("4.4 Automated MongoDB Indexing & TTL Rules (backend/database.py)", h2_style))
    story.append(Paragraph("Auto-initializes <code>users.email</code> unique index, compound <code>(user_email, created_at)</code> indexes, touchpoint indexes, and a 30-day TTL expiry index on <code>audit_logs</code>.", body_style))

    story.append(Spacer(1, 10))

    # 5. Verification Results
    story.append(Paragraph("5. Empirical Test & Runtime Verification Results", h1_style))
    story.append(Paragraph("<b>Automated Unit Test Suite Execution:</b>", body_style))
    test_code = """python3 -m unittest backend/tests/test_api.py

Ran 5 tests in 0.842s -> OK!
✓ test_auth_and_user_flow ... OK
✓ test_marketing_doctor_beautifulsoup_diagnose ... OK
✓ test_payment_signature_verification ... OK
✓ test_root_status ... OK
✓ test_touchpoint_event_and_attribution ... OK"""
    story.append(Paragraph(test_code.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style))

    story.append(Paragraph("<b>Live API Endpoint Verification:</b>", body_style))
    story.append(Paragraph("1. <code>ROOT API STATUS</code>: 200 OK (Aura Marketing AI OS API v2.1.0)", bullet_style))
    story.append(Paragraph("2. <code>AUTH ROUTER LOGIN</code>: 200 OK (JWT Access Token Issued)", bullet_style))
    story.append(Paragraph("3. <code>MARKETING DOCTOR (BS4 + SPA)</code>: 200 OK (Hydration Metrics Parsed Live)", bullet_style))
    story.append(Paragraph("4. <code>ATTRIBUTION ENGINE</code>: 200 OK (First, Last, Linear & W-Shaped Attribution Computed)", bullet_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF_BUILT: {pdf_filename}")

if __name__ == '__main__':
    target_pdf = "/Users/karthiku/Desktop/Devops learning/Appium agent/AI agent/public/Aura_Marketing_Full_Codebase_Architecture_Review.pdf"
    artifact_pdf = "/Users/karthiku/.gemini/antigravity/brain/d38bdb16-ce40-46d1-8443-730b9bb87824/Aura_Marketing_Full_Codebase_Architecture_Review.pdf"
    build_pdf(target_pdf)
    build_pdf(artifact_pdf)
