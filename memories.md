# Salvage AI — Memory & Progress Tracking (`memories.md`)

## 1. Project Overview & Mission
- **Project Name:** Salvage AI
- **Purpose:** An AI agent that finds and fixes revenue leaks in a merchant's PayPal subscription business (built for PayPal AI Hackathon).
- **Core Loop:** The agent proposes, the human approves, the system executes.
- **Repository Location:** `c:\Users\LENOVO\OneDrive\Desktop\Paypal`
- **Docs:**
  - `PRD (1).md`: Product requirements, user stories, functional specs (FR-1 through FR-21).
  - `ARCHITECTURE (2).md`: System components, data model, technology choices, invariants.
  - `DESIGN (3).md`: Frontend UI/UX, tokens, screen specifications, components.
  - `RULES (2).md`: Non-negotiable architectural & coding invariants.

---

## 2. Architectural Invariants
1. **Read-only LLM tools:** The LLM agent receives context and can only call read-only tools. It cannot write to PayPal or mutate subscription database states.
2. **Human-in-the-loop execution:** No state-changing PayPal API call can ever occur without an explicit, recorded human approval (`status='approved'`).
3. **Sandbox only:** Hardcoded live endpoints are strictly forbidden; live credentials are rejected unless explicitly overridden by `ALLOW_LIVE=true`.
4. **Deterministic detection:** Detection rules (R1 to R5) are pure deterministic code, not LLM judgments.
5. **Strict action enum:** Action types are constrained to a fixed enum (`RETRY_PAYMENT`, `REACTIVATE_SUBSCRIPTION`, `SUSPEND_SUBSCRIPTION`, `CANCEL_SUBSCRIPTION`, `SEND_DUNNING_MESSAGE`, `WIN_BACK_OFFER`, `REVIEW_DUPLICATE_FOR_REFUND`, `NO_ACTION`).
6. **Untrusted external data:** Customer-controlled text (names, emails, notes) is never placed in prompt instruction sections; only passed in delimited blocks.
7. **Idempotent operations:** Webhook ingestion and proposal executions must be safely replayable.
8. **Data honesty:** Simulated data and proxy ML models are visibly labelled across API responses and UI.

---

## 3. Current Implementation Status

### Backend (`/backend`)
- **Configuration & Guards (`app/config.py`):**
  - Pydantic Settings with env validation.
  - Guard preventing live credentials without `ALLOW_LIVE=true`.
- **Database (`app/db/`):**
  - SQLAlchemy models: `Plan`, `Subscriber`, `Subscription`, `Payment`, `WebhookEvent`, `Case`, `Proposal`, `ActionLog`, `ChurnScore`, `SyncState`.
  - SQLite default with foreign keys & WAL mode support.
- **PayPal Client (`app/paypal/`):**
  - OAuth token caching and auto-refresh before expiry.
  - Subscriptions API integration: get, activate, suspend, cancel, capture/retry outstanding balance.
  - Transaction Search API with 31-day chunked windowing.
  - Webhook signature verification via PayPal API.
- **Ingestion & Sync (`app/ingestion/`):**
  - Normalization of subscribers, subscriptions, plans, payments.
  - Idempotent webhook event recording and deduplication on `paypal_event_id`.
  - Subscription backfill and transaction search jobs.
- **Detection Engine (`app/detection/`):**
  - **R1:** Failed payment (payment-failed events or failed/suspended subscriptions).
  - **R2:** Stalled suspension (suspended longer than `stalled_days`, default 7).
  - **R3:** Duplicate charges (same subscriber, same amount, different transaction IDs within 72h).
  - **R4:** Price change fallout (cohort analysis before/after plan price change).
  - **R5:** At-risk subscriber (churn score above threshold, default 0.7).
  - **Severity Scoring:** Normalizes MRR (annual / 12) + urgency factor into a 0–100 integer score.
- **Churn Model (`app/churn/`, `scripts/train_churn.py`):**
  - Scikit-learn churn probability model (GradientBoosting / LogisticRegression).
  - Feature extraction from payment tenure, failed counts, billing interval.
- **Agent Runner (`app/agent/`):**
  - Anthropic tool-use runner with strict schema validation.
  - Compact context bundle builder and read-only tools (`get_subscription_timeline`, `get_plan_details`, `get_cohort_stats`, `get_churn_score`).
  - Fallback handling and `needs_review` marking on schema validation failures.
- **Executor Service (`app/executor/`):**
  - Idempotency checks to guarantee safe replays.
  - Param allow-lists per action type.
  - Clear separation between executable PayPal actions and advisory-only actions.
  - Comprehensive action logging (`action_log` table) and case resolution.
- **API Endpoints (`app/api/`):**
  - `/webhooks/paypal`: Signature verification, event logging, automated rule triggering.
  - `/sync`: Trigger subscription and transaction sync.
  - `/dashboard`: Metrics (revenue at risk, recovered revenue, risk by cause, priority cases).
  - `/cases`: Queue filtering, detail view, trigger agent diagnosis.
  - `/proposals`: Approve, edit, dismiss proposals.
  - `/actions`: Manual retry, list action logs.
  - `/demo`: Seed test data, inject failure scenarios (payment failure, duplicate charge, price change), reset DB.
  - `/healthz`: DB, PayPal auth, and LLM reachability check.

---

## 4. Key Fixes Applied
1. **`backend/tests/test_detection.py`:**
   - Fixed `test_high_mrr_no_urgency` where `mrr=300` (60% of max 500) correctly yields `severity=36`.
2. **`backend/app/executor/service.py`:**
   - Moved idempotency verification ahead of the `status != "approved"` check. Once a proposal is executed, its status changes to `"executed"`; checking idempotency first ensures repeat execution calls return the existing log instead of raising an error.
3. **`backend/tests/test_webhooks.py`:**
   - Corrected patch targets from `app.config.settings` to `app.api.webhooks.settings` to match module-level imports.
4. **SQLAlchemy 2.0 `Query.get()` Modernization:**
   - Replaced all legacy `db.query(Model).get(id)` with `db.get(Model, id)` across `detection/rules.py`, `executor/service.py`, `api/cases.py`, `api/proposals.py`, and `api/demo.py`. 0 legacy warnings.
5. **FastAPI Endpoints Added / Completed:**
   - Added `GET /api/proposals/{proposal_id}` to retrieve proposal details.
   - Enhanced `GET /api/dashboard` to return `priority_cases` (top 5 open/proposed cases by severity and MRR).
   - Added lazy import for `run_agent` in `api/cases.py` to prevent unnecessary Anthropic module load at startup.
6. **Sandbox Loopback Discovery & Resolution:**
   - Diagnosed root cause for `TestClient` hang on Windows sandbox: Windows AppContainer sandboxes block local loopback (`127.0.0.1`) socket pairs which `asyncio.ProactorEventLoop` self-pipes require (`socket.accept()`). Running integration tests with `BypassSandbox: true` completes instantaneously (3.9s).
   - **Full test suite status:** 59 passed, 0 failures, 100% green.

7. **Frontend Application Development (`/frontend`):**
   - Configured Node.js and npm runtime environment.
   - Scaffolded React 19 + TypeScript + Vite project configured with Tailwind CSS v4 design tokens from `DESIGN (3).md`.
   - Built comprehensive API client (`src/api/client.ts`) connecting all backend endpoints.
   - Implemented `Navbar` with active tabs, open-case badge count, and environment status indicator.
   - Implemented `DashboardView` with real-time revenue at risk, recovered revenue, horizontal "At risk by cause" bars, "Needs your attention" top priority queue, and data mix footer.
   - Implemented `CasesView` with multi-criteria filtering (status, leak cause type, keywords), sortable queue, and status badges.
   - Implemented `CaseDetailModal` featuring the side-by-side design: facts and raw evidence on the left, AI diagnosis, reasoning, drafted customer message, and plain-English Human-In-The-Loop approval dialog on the right.
   - Implemented `ActionLogView` providing an immutable audit trail of executed actions, recovered MRR, and PayPal response statuses.
   - Implemented `SettingsDemoView` with full Hackathon demo controls: seed sample subscribers, inject failure events (failed payment, stalled suspension, duplicate charge), sync subscriptions, and system health monitors.
   - Production build verified: `npm run build` generates clean dist bundle with 0 errors.

8. **Datetime Subtraction Normalization in Detection Rules (`rules.py`):**
   - Fixed `TypeError: can't subtract offset-naive and offset-aware datetimes` in SQLite environments by implementing `_ensure_utc()` helper across rules R1 and R2.

9. **API Response Schema Alignments:**
   - Synchronized frontend API client with backend paginated responses (`data.cases` in `/api/cases` and `data.actions` in `/api/actions`).
   - Mapped demo injector scenario keys to official PayPal webhook event types (`BILLING.SUBSCRIPTION.PAYMENT.FAILED`, `BILLING.SUBSCRIPTION.SUSPENDED`, etc.).

10. **Full End-to-End Lifecycle Test (`tests/test_e2e_flow.py`):**
    - Built comprehensive integration test simulating the entire workflow:
      1. Seed subscribers & active plans.
      2. Inject simulated payment failure event.
      3. Verify detection engine triggers and opens `FAILED_PAYMENT` case.
      4. Run read-only Claude diagnosis agent to propose `RETRY_PAYMENT`.
      5. Human merchant approves the proposal via `/api/proposals/{id}/approve`.
      6. Executor invokes PayPal client and captures outstanding balance.
      7. Case transitions to `resolved`.
      8. Dashboard `total_recovered_mrr` increments and audit log records execution.
    - **Total Test Suite Status:** 60 passed, 0 failures, 100% green.

11. **Backend API Case Detail Enrichment (`backend/app/api/cases.py`):**
    - Updated `_case_to_dict` to include nested `subscription`, `subscriber`, and `plan` details alongside full proposal attributes (`reasoning`, `customer_message`, `params`, `model`, `decided_at`, `decided_by`), eliminating "Unknown Subscriber" displays in the UI.
    - Extended `tests/test_e2e_flow.py` with explicit assertions validating subscriber, plan, subscription, and proposal payloads. All 60 tests passing green.

12. **Frontend Accessibility & UI/UX Polish (per `DESIGN (3).md`):**
    - Removed Vite boilerplate assets (`App.css`, `hero.png`, `react.svg`, `vite.svg`).
    - Added dark-theme CSS token values in `index.css` under `@media (prefers-color-scheme: dark)`.
    - Added keyboard navigation: `Escape` key closes dialogs and modals per WCAG AA / Section 9.
    - Added friendly empty queue state: "No leaks found. Nice." per Section 7.
    - Added visible `"Suggested by Salvage AI"` label and confidence rating on all AI recommendations per Section 8.
    - Added distinct button styles: "Mark as Handled" for advisory actions, danger styling for destructive actions (cancel/suspend confirmation), and "Approve & Execute" for PayPal API calls per Section 5.3.
    - Updated loading indicator to "Analyzing this case…" per Section 7.
    - Implemented accessible floating toast notification system with `role="status"` and `aria-live="polite"` for instant merchant action feedback.
    - Verified production build: `npm run build` generates 0 errors.

13. **Environment & Demo Setup (`backend/.env`):**
    - Created local `.env` with `DEMO_MODE=true`, `WEBHOOK_VERIFY=false`, `ADMIN_TOKEN=admin_secret_token_123` matching the frontend API client. Tested full live seeding and case listing.

---

## 5. Implementation Status & Checklist
- [x] **Backend Architecture & Invariants Verified:**
  - Read-only agent tools invariant enforced.
  - Human-in-the-loop approval gate enforced.
  - Sandbox-only protection active (`ALLOW_LIVE=false`).
  - Deterministic rules R1–R5 functioning accurately.
- [x] **Backend Cleanup & Tests Verification:** 60/60 tests passing across all unit and integration test suites.
- [x] **Frontend Development (`/frontend`):**
  - [x] Scaffold React + Vite + Tailwind CSS project according to `DESIGN (3).md`.
  - [x] Implement Dashboard (`/`):
    - Top stats: Monthly revenue at risk, Recovered revenue.
    - "At risk by cause" horizontal breakdown chart.
    - "Needs your attention" top priority queue.
    - Real vs. Simulated data badge.
  - [x] Implement Case Queue (`/cases`):
    - Filterable by type (Failed payment, Stalled, Duplicate, Price fallout, At-risk).
    - Sortable by severity and revenue.
  - [x] Implement Case Detail Modal/Page:
    - AI Diagnosis & Reasoning display.
    - Evidence and timeline drawer.
    - Drafted customer message (one-click copy).
    - Approve / Edit / Dismiss workflow.
  - [x] Implement Action Log (`/actions`):
    - Audit log of executed proposals, PayPal API responses, recovered MRR.
  - [x] Implement Demo Controls (`/settings` or overlay in Demo mode):
    - Seed sample merchant data.
    - Inject specific failure events on demand.
- [x] **End-to-End Verification:**
  - [x] Complete lifecycle integration test passing (`test_e2e_flow.py`).

---

## 6. Next Steps (Demo & Submission Preparation)
1. **Local Server Launch:**
   - Backend: `uvicorn app.main:app --reload --port 8000` (from `backend/`).
   - Frontend: `npm run dev` (from `frontend/`, opens on `http://localhost:3000`).
2. **Demo Storyboard Walkthrough (per `DESIGN (3).md` Section 11):**
   - Step 1: Open Dashboard — show revenue at risk & cause breakdown.
   - Step 2: Open Demo Controls — inject a failed payment webhook.
   - Step 3: Case appears in queue with High Severity badge.
   - Step 4: Open Case Detail — examine evidence, AI diagnosis, and customer message draft.
   - Step 5: Click "Approve & Execute" — show human confirmation dialog explaining the exact PayPal call.
   - Step 6: View Action Log — show HTTP response code and recovered MRR.
   - Step 7: Return to Dashboard — show recovered revenue increased and open leaks decreased.
3. **Demo Video Recording & Hackathon Submission:**
   - 3-minute video adhering to the storyboard in PRD / DESIGN.
   - Showcase sandbox security and human-in-the-loop safeguards.

