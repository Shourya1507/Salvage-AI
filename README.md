# Salvage AI

**An AI agent that finds and fixes revenue leaks in your PayPal subscription business.**

Built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/). Works entirely in the PayPal **sandbox**.

---

## The problem

Small subscription businesses lose recurring revenue to preventable causes: failed renewals, subscriptions stuck in suspension, duplicate charges, price-change fallout, and subscribers drifting toward cancellation. The data is in PayPal, but nobody has time to read it.

## What Salvage AI does

1. **Detects** leaks from transaction history (Transaction Search) and live webhook events.
2. **Diagnoses** each case with an LLM agent that explains what happened and what it is worth.
3. **Proposes** a specific fix and drafts the customer message.
4. **Acts** through the PayPal Subscriptions API, only after the merchant approves.

> The agent proposes. The human approves. The system executes.

## Features

- Dashboard: monthly revenue at risk by cause, open cases, recovered revenue
- Case queue sorted by severity, with the agent's reasoning and evidence
- One-click Approve / Edit / Dismiss
- Executable actions: retry payment, reactivate, suspend, cancel
- Advisory actions: dunning message, win-back offer, duplicate-charge review
- Full audit log of events, approvals, and PayPal responses
- Experimental churn-risk score (proxy-trained, clearly labelled)
- Demo mode with injectable failure scenarios

## How PayPal is used

| PayPal capability | Used for |
|---|---|
| OAuth 2.0 | Authenticating API calls |
| Subscriptions API | Reading subscriptions; suspend, activate, cancel; retrying outstanding balances |
| Transaction Search API | Backfilling payment history (31-day windows) |
| Webhooks | Real-time payment-failed, suspended, and cancelled events |

## How AI is used

An LLM agent receives a compact context bundle for each case and may call **read-only** tools (timeline, plan history, cohort stats, churn score). It returns a schema-validated proposal. It has **no ability to change PayPal state**.

## Architecture at a glance

```
PayPal Sandbox ──webhooks──▶ FastAPI backend ◀──REST── React dashboard
      ▲                         │   │   │
      └──Subscriptions/Search───┘   │   └──▶ LLM (read-only tools)
                                    ▼
                                Database
```

## Tech stack

Python 3.11 · FastAPI · SQLAlchemy (SQLite dev / Postgres deploy) · scikit-learn · React + Vite + Tailwind · Anthropic API (configurable model)

## Prerequisites

- Python 3.11+ and Node 20+
- A PayPal developer account with a **sandbox business account** and a **REST app**
  - In the app settings, enable **Subscriptions** and **Transaction Search**
- At least one sandbox **personal (buyer)** account
- An LLM API key
- A public HTTPS URL for webhooks (deploy, or use a tunnel such as ngrok)

## Quick start

```bash
git clone https://github.com/Shourya1507/Salvage-AI.git
cd Salvage-AI

# 1) Configure environment (see table below)
#    Create a .env file in backend/ with the variables listed.

# 2) Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.train_churn        # trains the proxy churn model
python -m scripts.create_plans       # creates sandbox product + plans
uvicorn app.main:app --reload --port 8000

# 3) Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open the dashboard at `http://localhost:5173`.

### Register the webhook

1. Expose the backend (deploy it, or run `ngrok http 8000`).
2. In the PayPal developer dashboard, add a webhook pointing to `https://<your-url>/webhooks/paypal`.
3. Subscribe it to the billing subscription and payment events.
4. Put the webhook ID in `PAYPAL_WEBHOOK_ID`.

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `PAYPAL_CLIENT_ID` | Sandbox REST app client ID | required |
| `PAYPAL_CLIENT_SECRET` | Sandbox REST app secret | required |
| `PAYPAL_ENV` | `sandbox` (live is blocked unless `ALLOW_LIVE=true`) | `sandbox` |
| `PAYPAL_WEBHOOK_ID` | ID of the registered webhook | required for verification |
| `WEBHOOK_VERIFY` | Verify webhook signatures. Set `false` **only** for simulator events in demo | `true` |
| `LLM_API_KEY` | API key for the LLM provider | required |
| `LLM_MODEL` | Model name | provider default |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///./salvage.db` |
| `DEMO_MODE` | Enables demo controls and endpoints | `false` |
| `EXECUTOR_ENABLED` | Global kill switch for PayPal write actions | `true` |
| `ADMIN_TOKEN` | Simple token protecting admin and demo routes | required |

Never commit `.env`.

## Data: what is real and what is simulated

This matters for judging, so we are explicit:

- **Real sandbox data:** a handful of subscriptions created and approved with sandbox buyer accounts. PayPal requires buyer approval to create a subscription, so we cannot bulk-create dozens by API alone.
- **Simulated data:** a larger synthetic set loaded into the local database and labelled `simulated` in the UI, so the dashboard and scoring work at a realistic scale.
- **Failure events:** injected via the PayPal Webhook Simulator or the in-app demo controls, because real sandbox payment failures are hard to trigger on demand. Simulated events may not pass signature verification, hence the labelled `WEBHOOK_VERIFY=false` demo option.
- **Churn model:** trained on the public IBM Telco Customer Churn dataset as a proxy. It demonstrates the pipeline and is not a validated predictor for PayPal subscribers.

## Running the demo

1. Set `DEMO_MODE=true` and start both servers.
2. In the dashboard's **Demo controls**, click **Load simulated subscribers**.
3. Click **Inject failed payment** (or send a simulator event from PayPal's dashboard).
4. Watch a case appear, open it, and read the agent's diagnosis and drafted message.
5. Click **Approve**. For a real sandbox subscription, the Subscriptions API call runs and the action log updates.
6. Check the dashboard: revenue at risk drops, recovered revenue rises.

## Project structure

```
salvage-ai/
├── README.md
├── memories.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── paypal/          # client, webhook verification
│   │   ├── ingestion/       # sync, backfill, normalizers
│   │   ├── detection/       # rules R1–R5, severity
│   │   ├── churn/           # model loading and scoring
│   │   ├── agent/           # prompts, tools, runner, schemas
│   │   ├── executor/        # approved-action execution
│   │   ├── api/             # routers
│   │   └── db/              # models, session
│   ├── scripts/             # create_plans, train_churn, load_simulated
│   └── tests/
└── frontend/
    └── src/                 # pages, components, api client
```

## API overview

Key routes: `POST /webhooks/paypal`, `GET /api/dashboard`, `GET /api/cases`, `POST /api/proposals/{id}/approve`.

## Safety design

- Agent has read-only tools; executing is a separate, human-approved step
- Fixed action enum and schema validation on all agent output
- Sandbox-only by default; live credentials are refused
- Idempotent webhook handling and action execution
- Customer-controlled text is treated as untrusted data
- Full audit trail

## Testing

```bash
cd backend && pytest
```

Includes unit tests for each detection rule, severity scoring, and schema validation, plus mocked-PayPal integration tests. An agent evaluation script runs golden cases against the LLM.

## Known limitations

- Sandbox only; no live merchants or real customers
- Hybrid real/simulated dataset (see above)
- Transaction Search can lag by up to about three hours; real-time behavior relies on webhooks
- Refunds are advisory only
- Messages are drafted, not sent
- Single-merchant, no multi-user auth

## License

MIT License
