# ADR: Invoi — Web App Migration

**Status:** Draft
**Date:** 2026-04-02
**Author:** Sarah (developer)
**Supersedes:** `docs/Invoice-Builder-ADR.md` (desktop-only app for Lisa)

---

## Context

Lisa's invoice app (`lisa-invoice-app`) is a working local desktop tool: Flask backend, React (Vite) frontend, PyInstaller `.exe`, Gmail app-password email. It generates weekly invoices and monthly reports for a single 1099 home health aide contractor.

The app works but has inherent limitations:

- **No mobile access.** Lisa wants to invoice from her phone. The `.exe` is desktop-only.
- **Distribution is painful.** GitHub Releases, SmartScreen warnings, Google Drive virus scanning — every step is friction.
- **Email setup is fragile.** Gmail app passwords require precise formatting, no dashes, and a multi-step Google account configuration that non-technical users struggle with.
- **Single user, single client.** The `config.json` flat-file model doesn't extend to multiple users.
- **Industry-locked.** The UI has home health aide–specific language (patient name, care objectives, medications). The core workflow — enter hours, generate invoice, email it — applies to any hourly contractor.

The decision is to migrate the app to a multi-user web application under the brand **Invoi** (`goinvoi.com`), serving any hourly 1099 contractor across industries.

---

## Decision

Build a serverless web application on AWS that:

- Serves the React SPA as static files via S3 + CloudFront
- Runs backend logic (PDF generation, email, data access) as Python Lambda functions behind API Gateway
- Stores user data in DynamoDB and generated PDFs in S3
- Authenticates users via Google OAuth (Cognito or equivalent), eliminating app passwords entirely
- Supports multiple users, multiple clients per user, and industry-agnostic invoicing
- Is accessible from any device with a browser — phone, tablet, laptop, desktop
- Replaces the `.exe` distribution model completely

---

## Brand

| | |
|---|---|
| **Name** | Invoi |
| **Domain** | goinvoi.com |
| **Tagline** | TBD — something like "Invoicing for people who work by the hour" |
| **Target audience** | 1099 hourly contractors: home health aides, tutors, cleaners, handypeople, personal trainers, pet sitters, freelance service workers |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      CloudFront CDN                      │
│              (serves static React app + assets)          │
│                    goinvoi.com → S3                       │
└──────────────────────────┬──────────────────────────────┘
                           │
              static files │  API calls
              (S3 bucket)  │  (api.goinvoi.com)
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                     API Gateway                          │
│                  (REST or HTTP API)                       │
└──────────────────────────┬──────────────────────────────┘
                           │
              ┌────────────┼────────────────┐
              ▼            ▼                ▼
         ┌─────────┐ ┌──────────┐   ┌────────────┐
         │ Lambda:  │ │ Lambda:  │   │ Lambda:    │
         │ config   │ │ invoice  │   │ email      │
         │ /auth    │ │ /pdf     │   │ /send      │
         └────┬─────┘ └────┬─────┘   └─────┬──────┘
              │            │                │
    ┌─────────┼────────────┼────────────────┼──────────┐
    │         ▼            ▼                ▼          │
    │    DynamoDB     S3 (PDFs)           SES          │
    │   (user data,   (generated          (send        │
    │    invoices,    invoices &           invoices     │
    │    config)      reports)            & reports)    │
    └──────────────────────────────────────────────────┘
```

### Why Serverless on AWS?

| Concern | Decision | Rationale |
|---|---|---|
| Compute | Lambda (Python 3.12) | No idle cost. Free tier covers 1M requests/month. Existing Python code (ReportLab, email logic) ports directly. |
| Static hosting | S3 + CloudFront | Vite builds to static files. Pennies/month. Global CDN. |
| Database | DynamoDB | Free tier: 25GB + 200M requests/month. No server to manage. Pay-per-request pricing after free tier. |
| Email | SES | $0.10/1,000 emails. Eliminates Gmail app passwords entirely. Users authenticate with Google OAuth; Invoi sends on their behalf via SES. |
| PDF storage | S3 | Generated PDFs stored per-user. Signed URLs for downloads. Practically free at this scale. |
| Auth | Cognito w/ Google OAuth | "Sign in with Google" → user is authenticated AND we have their email for sending. One-step onboarding. |
| Infrastructure-as-code | SST (Serverless Stack) or AWS CDK | Defines all resources in code. SST is purpose-built for this exact pattern (React SPA + Lambda API + S3). |

**Estimated cost at 10–100 users:** Under $2/month. Potentially $0 within AWS free tier for the first year.

**Alternatives considered:**

| Option | Why not |
|---|---|
| Railway / Render | $5–20/month for idle servers. Unknown platforms with less control. |
| Flask on EC2/Fargate | Paying for 24/7 compute when the app is used sporadically (a few minutes per week per user). |
| Next.js on Vercel | Would require rewriting all Python backend logic (ReportLab, email) in JavaScript. JS PDF ecosystem is less mature. |
| Firebase | Viable, but vendor-locks to Google's specific patterns. Less transferable knowledge than AWS. |

---

## Migration Strategy

### What Carries Over (Unchanged)

- **React frontend** (`App.jsx` v10+) — the entire UI, templates, profile page, weekly/monthly editors. Only change: swap `fetch("http://localhost:5000/api/...")` → `fetch("https://api.goinvoi.com/api/...")`.
- **PDF templates** — all 7 theme palettes (Morning Light, Caring Hands, Garden, Golden Hour, Lavender Eve, Coastal, Terracotta) and their HTML templates. ReportLab rendering logic carries over as-is inside Lambda.
- **Email body templates** — `create_weekly_email_body()`, `create_monthly_email_body()` in `mail_service.py`.
- **Theme registry** — `themes.py` with all palette definitions.
- **Core business logic** — week calculation, invoice numbering, scan-month aggregation, sidecar JSON pattern.

### What Changes

| Component | Desktop (current) | Web (Invoi) |
|---|---|---|
| **Backend** | Flask (single process) | Lambda functions behind API Gateway |
| **Data storage** | `config.json` flat file | DynamoDB (per-user records) |
| **PDF storage** | Local filesystem | S3 bucket (per-user prefix) |
| **Email** | Gmail SMTP + app password | AWS SES (authenticated via Cognito) |
| **Auth** | None (single user) | Google OAuth via Cognito |
| **Distribution** | `.exe` via GitHub Releases | `goinvoi.com` (browser) |
| **PDF rendering** | ReportLab (local) | ReportLab (Lambda layer) |
| **Client model** | Single client in config | Multi-client per user in DynamoDB |
| **Industry** | Home health aide–specific | Industry-agnostic (occupation selector) |

### What Gets Sunset

- **PyInstaller build pipeline** and `build.bat`
- **GitHub Actions `.exe` workflow**
- **`.env` with Gmail app passwords**
- **`config.json` flat file**
- **Heartbeat watchdog** (desktop-only browser lifecycle management)
- **localhost:5000 serving pattern**

---

## Data Model (DynamoDB)

### Users Table

**Partition key:** `userId` (Cognito sub)

```json
{
  "userId": "google-oauth2|abc123",
  "email": "lisa@gmail.com",
  "name": "Lisa Wadley",
  "address": "123 Main St, Denver, CO 80201",
  "personalEmail": "lisa@email.com",
  "rate": 28.00,
  "occupation": "home-health",
  "accent": "#b76e79",
  "template": "morning-light",
  "invoiceNote": "Thank you for your business.",
  "signatureFont": "Dancing Script",
  "accountantEmail": "accountant@cpa.com",
  "invoiceNumberConfig": {
    "prefix": "INV",
    "includeYear": false,
    "separator": "-",
    "padding": 3,
    "nextNum": 1
  },
  "paymentTerms": "receipt",
  "taxEnabled": false,
  "taxRate": 0,
  "taxLabel": "Sales Tax",
  "logoKey": "users/abc123/logo.png",
  "logoSize": "medium",
  "clients": [
    {
      "id": "client_abc",
      "name": "Sunrise Home Health Agency",
      "email": "billing@sunrisehh.com",
      "address": "",
      "defaultShift": { "start": "09:00", "end": "17:00", "days": ["Mon","Tue","Wed","Thu","Fri"] }
    }
  ],
  "activeClientId": "client_abc",
  "createdAt": "2026-04-02T00:00:00Z",
  "plan": "free"
}
```

### Invoices Table

**Partition key:** `userId`
**Sort key:** `invoiceId` (e.g., `INV-20260324` or `RPT-2026-03`)

```json
{
  "userId": "google-oauth2|abc123",
  "invoiceId": "INV-20260324",
  "invoiceNumber": "INV-047",
  "clientId": "client_abc",
  "type": "weekly",
  "status": "sent",
  "weekStart": "2026-03-24",
  "weekEnd": "2026-03-30",
  "dueDate": "2026-03-30",
  "paymentTerms": "receipt",
  "dailyHours": { "Mon": 8, "Tue": 8, "Wed": 8, "Thu": 8, "Fri": 8, "Sat": 0, "Sun": 0 },
  "totalHours": 40,
  "rate": 28.00,
  "subtotal": 1120.00,
  "taxRate": 0,
  "taxAmount": 0,
  "totalPay": 1120.00,
  "template": "morning-light",
  "pdfKey": "users/abc123/weekly/INV-20260324.pdf",
  "logPdfKey": "users/abc123/logs/LOG-20260324.pdf",
  "sentAt": "2026-03-30T14:22:00Z",
  "sentTo": ["billing@sunrisehh.com"],
  "paidAt": null,
  "createdAt": "2026-03-30T14:20:00Z"
}
```

### Access Patterns

| Query | Key condition |
|---|---|
| Get user profile | `userId = X` (Users table) |
| List all invoices for user | `userId = X` (Invoices table) |
| Get specific invoice | `userId = X AND invoiceId = Y` |
| Scan month for report | `userId = X AND invoiceId BETWEEN INV-20260301 AND INV-20260331` |
| List invoices for client | `userId = X` + filter on `clientId` |
| Filter by status | `userId = X` + filter on `status` |
| Calendar view (month) | `userId = X AND invoiceId BETWEEN INV-YYYYMM01 AND INV-YYYYMM31` |
| Overdue invoices | `userId = X` + filter: `status = sent AND dueDate < today` |
| Bulk export by date range | `userId = X AND invoiceId BETWEEN start AND end` |

---

## API Endpoints

All endpoints require Cognito JWT in `Authorization` header.

### Config / Profile

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/config` | Return user profile from DynamoDB |
| `POST` | `/api/config` | Update user profile |

### Invoices

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/invoices` | List all invoices (paginated, filterable by status/client/date range) |
| `GET` | `/api/invoices/{invoiceId}` | Get single invoice metadata + associated log/report references |
| `POST` | `/api/submit/weekly` | Generate PDF, store in S3, save metadata, optionally send email. Uses `TransactWriteItems` to atomically increment invoice number and create record. |
| `POST` | `/api/submit/monthly` | Generate monthly report PDF, store, optionally send |
| `PATCH` | `/api/invoices/{invoiceId}/status` | Update invoice status (mark paid, etc.) |
| `POST` | `/api/invoices/bulk` | Bulk actions: mark paid, resend, export |
| `GET` | `/api/scan-month?year=2026&month=3` | Scan for existing weekly invoices in a given month |

### PDF / Export

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/pdf/{invoiceId}` | Return signed S3 URL for PDF download |
| `POST` | `/api/export` | Generate ZIP or CSV of selected invoices, return signed S3 URL |

### Logo

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/logo` | Upload logo image, store in S3, update user record |
| `DELETE` | `/api/logo` | Remove logo |

### Smart Logs (Pro)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/logs/transcribe` | Voice memo → structured log entry (Pro only) |
| `POST` | `/api/logs/reformat` | Rough notes → professional formatted log (Pro only) |
| `POST` | `/api/logs/ocr` | Photo of handwritten notes → text → formatted log (Pro only) |

---

## Authentication Flow

```
User clicks "Sign in with Google"
        │
        ▼
Cognito Hosted UI (Google OAuth)
        │
        ▼
Google authenticates → returns tokens
        │
        ▼
Cognito issues JWT (id_token + access_token)
        │
        ▼
React app stores tokens, includes in API calls
        │
        ▼
API Gateway validates JWT automatically
        │
        ▼
Lambda receives userId from token claims
```

**Key benefit:** The user's Gmail address is captured during OAuth. SES can send emails "from" their address (after domain/email verification) without them ever configuring an app password. This is the single biggest UX improvement over the desktop app.

**SES sending identity options:**
1. **Verified email identity** — each user verifies their email with SES (one-time click in a confirmation email). Invoi then sends invoices "from" their address.
2. **Verified domain identity** — Invoi sends from `noreply@goinvoi.com` with the user's name in the "From" display name. Simpler but less personal.
3. **Hybrid** — default to option 2, let users verify their own email for option 1 if they want.

**Recommendation:** Start with option 2 (domain identity). It requires zero user action beyond signing in. Upgrade to per-user email verification later as a premium feature.

---

## Industry-Agnostic Design

The existing occupation selector in ProfilePage already supports this. Current occupations:

- Home Health Aide
- Tutor / Instructor
- Personal Trainer
- House Cleaner
- Pet Sitter / Dog Walker
- Handyperson
- Caregiver
- Other

**What changes per occupation:**

| Element | How it adapts |
|---|---|
| Invoice label | "Contractor Invoice" (default) or "Service Invoice" |
| Client field label | "Client" / "Agency" / "Family" depending on occupation |
| Log template fields | Care-specific fields (meds, patient) only shown for health occupations |
| Hour entry labels | "Hours" for all; optional shift start/end for shift-based work |

**What stays the same regardless of occupation:**

- Weekly invoice generation from daily hours
- Monthly report aggregation
- Email delivery flow
- Template selection and theming
- PDF layout structure

---

## Feature Requirements

### Design Philosophy

Every feature must invoke three feelings simultaneously: **productivity** (I'm getting things done), **amusement** (this is delightful to use), and **relaxation** (I don't have to think hard). Reasonable defaults everywhere. Streamline and abstract simultaneously. If a feature requires a paragraph of explanation, it's designed wrong.

---

### Invoice Numbering (Custom Codes)

Users should be able to bring their own numbering system. If they've been doing `LISA-001`, `LISA-002` for years, Invoi picks up where they left off.

**UX: Visual builder, not a format string.** No curly braces, no tokens. The UI is:

1. **Prefix** — editable text input (default: `INV`)
2. **Include year?** — toggle (default: off)
3. **Separator** — visual selector: `-` `/` or none (default: `-`)
4. **Starting number** — editable input so users can type `047` to pick up from their existing system
5. **Number padding** — visual selector showing `001` vs `0001` vs `01` (default: `001`)
6. **Live preview** — updates in real-time as they adjust: `INV-001` → `INV-002` → `INV-003`

This lives in an **"Advanced settings"** section within Profile — collapsed by default so it doesn't overwhelm new users. The default (`INV-001` with auto-increment) works out of the box.

**Backend:** The user record stores `invoiceNumberConfig: { prefix, includeYear, separator, padding, nextNum }`. On each invoice creation, a DynamoDB `TransactWriteItems` call atomically increments `nextNum` and creates the invoice record, guaranteeing no duplicate numbers even under concurrent requests.

---

### Invoice History: Calendar View + List View + Focus View

Three lenses on the same data — same underlying query, different presentations. A segmented control at the top of the History page lets users switch between them.

**Calendar View (default)**

A month grid where each day cell shows color-coded invoice pills:

| Color | Status | Visual |
|---|---|---|
| Gray | Draft (saved, not sent) | Muted pill |
| Blue | Sent (awaiting payment) | Solid pill |
| Green | Paid | Pill with small checkmark |
| Red | Overdue (past due date, unpaid) | Pill with alert accent |

Each pill shows a condensed summary: client initials, total hours, total amount. Tapping a pill opens the invoice detail panel. Month navigation (‹ ›) matches the existing MonthlyPage pattern.

**List View**

Filterable, sortable table/card list. Filters: status (draft/sent/paid/overdue), client, date range. Multi-select for bulk actions: mark as paid, export as ZIP, resend email. Each row/card expands to show full invoice detail, associated logs, and the monthly report that includes it (if one exists). Users can navigate sequentially between invoices from the detail view (← prev / next →) and exit back to the list.

**Focus View**

The calendar grid, collapsed to show only days with invoice activity. Days without invoices are removed. Remaining days display side by side as cards in a tight horizontal/grid layout — like a filmstrip of your invoicing activity. Same color coding and metadata as calendar view, but with more room per card to show details (client name, hours breakdown, amount, status badge). This view answers: "Show me just my invoices, nothing else, with all the context I need."

This is the view that makes Invoi feel different from competitors. Nobody else has this.

---

### Payment Status Tracking

Each invoice has a `status` field: `draft` | `sent` | `paid` | `overdue`.

- **Draft** — saved but not emailed. Default state on creation.
- **Sent** — emailed to client. Auto-set when email sends successfully.
- **Paid** — manually toggled by user (one-tap in any view).
- **Overdue** — auto-calculated: status is `sent` AND current date > due date.

The status toggle is accessible from every view (calendar pill, list row, focus card, invoice detail). Marking as paid shows a small celebratory micro-animation (confetti? checkmark bloom?) because getting paid should feel good.

---

### Due Dates and Payment Terms

Profile-level default that stamps onto each invoice. Options presented as friendly presets:

- Due on receipt (default)
- Net 7
- Net 15
- Net 30
- Custom (user enters number of days)

The due date is calculated automatically from the invoice send date and displayed on the PDF. The `overdue` status is derived from this.

**Future consideration:** Net 30 with accruing interest clauses. This requires legal language on the invoice PDF and potentially state-specific compliance. Parking this as a later Pro feature that would need legal review.

---

### Logo Upload

Profile section with drag-and-drop or file picker. The UI shows:

1. Upload area with size/format recommendations ("PNG or SVG, at least 300×300px for sharp rendering")
2. **Resize slider** — adjusts logo size on the invoice (small / medium / large)
3. **Live preview** — shows the logo rendered on a mini invoice mockup using their active template, so they see exactly how it'll look before saving

Logo is stored in S3 at `users/{userId}/logo.{ext}`. The PDF templates pull it from S3 at render time. Free tier includes logo; this isn't a paywalled feature.

---

### Tax Line

Toggle in Profile: "Charge sales tax?" (default: off). When enabled:

- Tax rate % input (e.g., `8.25`)
- Optional tax label (e.g., "Sales Tax", "GST", "VAT")
- Invoice PDF adds a subtotal line, tax line, and adjusted total
- Tax is calculated on the hours × rate subtotal

This is a display feature, not a tax engine. Invoi doesn't determine what rate to charge or whether the user needs to collect tax — that's their responsibility.

---

### Default Shift → Invoice Prefill

The existing flow: logs prepopulate the weekly invoice. The new fallback: if no logs exist for a week, the user's **default shift** (already defined per-client in Profile) fills out the weekly hours automatically.

Example: Client "Sunrise Agency" has a default shift of 9:00–17:00 (8 hours), Mon–Fri. When the user opens a new weekly invoice for Sunrise with no logs on file, the invoice pre-fills with 8 hours × 5 days = 40 hours. The user can adjust any day before submitting.

This means a user with a consistent schedule can generate an invoice in literally two taps: open week → submit.

---

### Smart Log Features (Pro)

For Pro users, the service log gets intelligence:

- **Voice-to-log transcription** — user records a voice memo after a shift, Invoi transcribes and formats it into a structured service log entry. Especially valuable for home health aides and caregivers documenting patient care on the go.
- **Note reformatting** — user types rough notes, Invoi cleans them up for consistency and professional tone while preserving meaning. Matches the visual branding of their chosen template.
- **Import written notes** — photo of handwritten notes → OCR → formatted log entry.

Implementation: These features call an AI API (Anthropic or similar) from a dedicated Lambda function. Token costs are absorbed into the Pro subscription price.

---

### Export and Bulk Actions

From the list view, users can select multiple invoices and:

- **Export as ZIP** — downloads a ZIP of selected PDFs (invoices + associated logs + monthly reports)
- **Export as CSV** — tabular export of invoice data (date, client, hours, amount, status) for accountants at tax time
- **Mark as paid** — bulk status update
- **Resend** — re-email selected invoices

The filter tools in list view complement export naturally: "filter to Q1 2026 → select all → export CSV" gives the accountant exactly what they need.

---

## Pricing Model (Future)

Not implemented at launch, but the architecture supports it:

| Tier | Price | Includes |
|---|---|---|
| **Free** | $0 | 4 invoices/month, 1 client, Invoi branding on PDF footer, email from `noreply@goinvoi.com`, all templates, logo upload, calendar/list/focus views, payment tracking, export |
| **Pro** | $5–8/month or $49/year | Unlimited invoices, unlimited clients, custom email identity (send from your own address), no branding, voice-to-log transcription, note reformatting, handwriting import, priority support |

**Implementation:** `plan` field on user record. Lambda checks plan limits before generating PDFs. Stripe for payment processing (future). AI log features gated behind plan check before calling transcription/reformatting Lambda.

---

## Repository Structure (Post-Migration)

```
invoi/
├── frontend/
│   ├── src/
│   │   └── App.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── backend/
│   ├── functions/
│   │   ├── config.py          ← GET/POST /api/config
│   │   ├── submit_weekly.py   ← POST /api/submit/weekly (TransactWriteItems)
│   │   ├── submit_monthly.py  ← POST /api/submit/monthly
│   │   ├── scan_month.py      ← GET /api/scan-month
│   │   ├── invoices.py        ← GET /api/invoices, /api/invoices/{id}, PATCH status
│   │   ├── pdf.py             ← GET /api/pdf/{id} (signed URL)
│   │   ├── export.py          ← POST /api/export (ZIP/CSV generation)
│   │   ├── logo.py            ← POST/DELETE /api/logo
│   │   └── smart_logs.py      ← POST /api/logs/transcribe, /reformat, /ocr (Pro)
│   ├── services/
│   │   ├── pdf_service.py     ← ReportLab rendering (ported from desktop)
│   │   ├── mail_service.py    ← SES email (replaces SMTP)
│   │   └── db_service.py      ← DynamoDB read/write helpers
│   ├── templates/
│   │   └── (HTML invoice templates — all 7 palettes × 3 doc types)
│   ├── themes.py              ← Theme registry (carried over)
│   └── requirements.txt
├── infra/
│   ├── sst.config.ts          ← SST infrastructure definition
│   └── stacks/
│       ├── api.ts             ← API Gateway + Lambda stack
│       ├── storage.ts         ← S3 + DynamoDB stack
│       ├── auth.ts            ← Cognito stack
│       └── web.ts             ← CloudFront + S3 static site stack
├── docs/
│   ├── ADR-webapp-migration.md  ← This document
│   └── Invoice-Builder-ADR.md   ← Original desktop ADR (archived)
├── .gitignore
├── package.json               ← Root: SST + workspace config
└── README.md
```

---

## Migration Phases

### Phase 0: Foundation (do first)

- [ ] Register `goinvoi.com` domain
- [ ] Create AWS account (or use existing) with billing alerts
- [ ] Initialize SST project with basic stacks (S3, CloudFront, API Gateway, Lambda)
- [ ] Deploy "hello world" Lambda behind API Gateway
- [ ] Deploy static React build to S3/CloudFront
- [ ] Verify end-to-end: browser loads React app, React app calls Lambda, Lambda responds

### Phase 1: Auth + Profile

- [ ] Set up Cognito User Pool with Google OAuth provider
- [ ] Add sign-in/sign-out flow to React app
- [ ] Create DynamoDB Users table
- [ ] Port `GET /api/config` and `POST /api/config` to Lambda + DynamoDB
- [ ] Wire React ProfilePage to live API
- [ ] Verify: user can sign in, save profile, reload and see saved data

### Phase 2: Invoice Generation + Numbering

- [ ] Package ReportLab as Lambda layer
- [ ] Port `pdf_service.py` to Lambda-compatible format
- [ ] Create DynamoDB Invoices table
- [ ] Implement invoice number config on user record with visual builder UI
- [ ] Implement `TransactWriteItems` for atomic number increment + invoice creation
- [ ] Port `POST /api/submit/weekly` — generate PDF with custom invoice number, store in S3, save metadata
- [ ] Implement default shift → invoice prefill fallback (when no logs exist)
- [ ] Port `GET /api/scan-month` — query DynamoDB instead of scanning filesystem
- [ ] Port `POST /api/submit/monthly` — aggregate and generate report
- [ ] Wire React WeeklyPage and MonthlyPage to live API
- [ ] Add payment terms selector to Profile (presets: receipt, net 7/15/30, custom)
- [ ] Add tax toggle + rate/label to Profile
- [ ] Update PDF templates to render due date, tax line, and custom invoice number
- [ ] Verify: user can create invoice with custom number, preview PDF, save to S3

### Phase 3: Email + Status Tracking

- [ ] Verify `goinvoi.com` domain with SES
- [ ] Port `mail_service.py` from SMTP to SES (`boto3.client('ses')`)
- [ ] Wire "Save & Send" flow end-to-end
- [ ] Implement invoice status model (draft/sent/paid/overdue)
- [ ] Auto-set `sent` on successful email, auto-calculate `overdue` from due date
- [ ] Add one-tap "mark as paid" toggle to invoice detail
- [ ] Verify: invoice PDF is emailed from `noreply@goinvoi.com`, status updates correctly

### Phase 4: History Views + Logo

- [ ] Build History page with segmented control (Calendar / List / Focus)
- [ ] Calendar view: month grid, color-coded pills per status, tap to open detail
- [ ] List view: filterable/sortable, multi-select, bulk actions (mark paid, export, resend)
- [ ] Focus view: collapsed calendar showing only invoice days as side-by-side cards
- [ ] Invoice detail panel: full doc preview, associated logs, monthly report link, sequential navigation (← →)
- [ ] Implement logo upload (S3 storage, resize slider, live preview on mini invoice mockup)
- [ ] Update PDF templates to render logo at user-selected size
- [ ] Implement export: ZIP of selected PDFs, CSV of invoice data
- [ ] `PATCH /api/invoices/{id}/status` endpoint
- [ ] `POST /api/export` endpoint

### Phase 5: Polish + Lisa Migration

- [ ] Industry-agnostic label pass on all UI text
- [ ] Landing page / marketing page at `goinvoi.com`
- [ ] Migrate Lisa's existing data (config + saved invoices) to her new Invoi account
- [ ] Walk Lisa through the new sign-in flow
- [ ] Sunset the `.exe` — archive the desktop ADR, remove PyInstaller pipeline

### Phase 6: Launch Prep

- [ ] Privacy policy and terms of service (required for Google OAuth)
- [ ] Error monitoring (CloudWatch alarms on Lambda errors)
- [ ] Rate limiting on API Gateway
- [ ] Invite 5–10 beta users from contractor communities
- [ ] Collect feedback, iterate

### Phase 7: Pro Features (Post-Launch)

- [ ] Stripe integration for Pro subscriptions
- [ ] Custom email identity (per-user SES email verification)
- [ ] Voice-to-log transcription Lambda (AI-powered)
- [ ] Note reformatting Lambda (AI-powered)
- [ ] Handwriting OCR → formatted log Lambda (AI-powered)
- [ ] Interest clause builder for payment terms (requires legal review)
- [ ] Plan-gated feature checks in all relevant Lambda functions

---

## Open Questions

1. **Logo / visual identity** — Needs design. The "i" in Invoi has natural logo potential (pen nib, checkmark, person).
2. **Custom email identity** — Should free-tier users be able to verify their own email with SES, or is that a Pro feature? Current recommendation: Pro feature.
3. **Offline / local backup** — Should the web app have any offline capability, or is "you need internet" acceptable? (Most competitors require internet.)
4. **Existing `.exe` users** — Lisa is currently the only user. Migration is a phone call. If others had the `.exe`, we'd need a data migration path.
5. **Flutter native apps** — Sarah has more Flutter experience than React. If native mobile apps become necessary, Flutter targeting iOS + Android from a single codebase is a viable future path (following Invoice Ninja's architecture: shared API, separate frontends). Not in scope for initial launch.
6. **Focus view layout** — Horizontal scroll strip vs. responsive grid for the collapsed calendar view? Needs prototyping to see what feels best on mobile vs. desktop.
7. **"Mark as paid" micro-animation** — What's the right celebratory moment? Confetti? Checkmark bloom? Subtle color wash? Should match the relaxation/amusement design philosophy without being cheesy.
8. **Invoice number reset on year change** — Should `nextNum` auto-reset to 1 on January 1 when `includeYear` is enabled? Or always increment globally? Users probably expect reset, but it could cause confusion if they switch the toggle mid-year.
9. **Voice transcription quality/cost** — What's the acceptable latency and cost per transcription for Pro users? Need to benchmark Anthropic API vs. Whisper vs. other options.

---

## What Is NOT In Scope (v1 Launch)

- Native mobile apps (iOS/Android) — the browser is sufficient for launch
- Payment processing (Stripe integration) — not until pricing tiers are implemented (Phase 7)
- Multi-currency / international invoicing
- Tax calculation or 1099 form generation (we display a user-set tax rate, we don't calculate what it should be)
- Time tracking / clock-in/clock-out
- Client portal (where clients view/pay invoices online)
- Accounting integrations (QuickBooks, Xero, Wave)
- AI log features (voice transcription, note reformatting, OCR) — Pro tier, Phase 7
- Interest clause builder — requires legal review, Phase 7+
- Line-item invoicing (Invoi bills hours, not itemized products)
- Recurring/scheduled invoice auto-send

---

## Competitive Positioning

| Competitor | Price | Positioning | Invoi's edge |
|---|---|---|---|
| Invoice Ninja | Free (5 clients) / $10+/mo | Full-featured, power-user oriented | Simpler. Zero learning curve. Opinionated workflow. |
| Wave | Free | Full accounting suite with invoicing | Way simpler. Not trying to be accounting software. |
| Invoice Simple | Free / $10+/mo | Mobile-first invoice generator | More structured workflow (weekly hours → invoice → email, not ad-hoc). |
| FreshBooks | $7+/mo | Established SaaS for freelancers | Cheaper (free tier). Purpose-built for hourly contractors. |
| invoice-builder.com | Free / $29/yr | Basic form-to-PDF generator | Persistent data, email delivery, monthly reports, themes. Actually a product, not a form. |

**Invoi's value proposition:** The only invoicing tool designed specifically for hourly contractors who submit the same type of invoice every week. Not a general-purpose invoice generator. Not an accounting suite. Enter your hours, pick your template, hit send. Beautiful calendar and focus views that make invoice history feel organized instead of overwhelming. Smart defaults that mean a consistent-schedule contractor can generate an invoice in two taps. And a Pro tier with AI-powered log transcription that no competitor offers.

---

## References

- Original desktop ADR: `docs/Invoice-Builder-ADR.md`
- SST documentation: https://sst.dev
- AWS Lambda Python: https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html
- Cognito + Google OAuth: https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-social-idp.html
- SES sending: https://docs.aws.amazon.com/ses/latest/dg/send-email.html
- ReportLab on Lambda: package as Lambda layer with `reportlab` wheel
