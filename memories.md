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

---

## 5. Next Steps & Remaining Tasks
- [ ] **Tests Verification:** Run backend unit and integration test suite (`pytest tests/test_agent.py tests/test_detection.py tests/test_executor.py`).
- [ ] **Frontend Development (`/frontend`):**
  - Scaffold React + Vite + Tailwind CSS project according to `DESIGN (3).md`.
  - Implement Dashboard (`/`):
    - Top stats: Monthly revenue at risk, Recovered revenue.
    - "At risk by cause" horizontal breakdown chart.
    - "Needs your attention" top priority queue.
    - Real vs. Simulated data badge.
  - Implement Case Queue (`/cases`):
    - Filterable by type (Failed payment, Stalled, Duplicate, Price fallout, At-risk).
    - Sortable by severity and revenue.
  - Implement Case Detail Modal/Page:
    - AI Diagnosis & Reasoning display.
    - Evidence and timeline drawer.
    - Drafted customer message (one-click copy).
    - Approve / Edit / Dismiss workflow.
  - Implement Action Log (`/actions`):
    - Audit log of executed proposals, PayPal API responses, recovered MRR.
  - Implement Demo Controls (`/settings` or overlay in Demo mode):
    - Seed sample merchant data.
    - Inject specific failure events on demand.
- [ ] **End-to-End Verification:**
  - Verify complete workflow: Webhook/demo trigger -> Case creation -> Agent diagnosis -> Human approval -> Execution -> Action log -> Dashboard update.

