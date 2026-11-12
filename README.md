# Salvage AI — Autonomous PayPal Subscription Revenue Recovery Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-salvage--ai.onrender.com-green)](https://salvage-ai.onrender.com/)

> **The AI Proposes → The Human Approves → The System Executes**

Salvage AI is an autonomous agent that detects silent revenue leaks in PayPal subscription businesses, diagnoses root causes using Google Gemini 2.5 Flash, and recovers lost Monthly Recurring Revenue (MRR) with human-in-the-loop safety.

## 🚀 Live Demo

**[https://salvage-ai.onrender.com/](https://salvage-ai.onrender.com/)**

The live demo runs in full demo mode with simulated PayPal sandbox data. Use the **Demo Controls** tab to:
1. **Seed Subscribers** — Generate 25 sample subscribers with plans and payments.
2. **Inject Failures** — Simulate failed payments, stalled suspensions, or duplicate charges.
3. **Review AI Diagnosis** — Open a case to see Gemini's analysis and recovery proposal.
4. **Approve & Execute** — Click to approve the AI's recommendation and recover revenue.

---

## 🛠️ Local Setup & Run Instructions

### Prerequisites

- **Python 3.11+**
- **Node.js 20.19+** (or 22+)
- **Git**

### 1. Clone the Repository

```bash
git clone https://github.com/Shourya1507/Salvage-AI.git
cd Salvage-AI
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory:

```env
DEMO_MODE=true
WEBHOOK_VERIFY=false
ADMIN_TOKEN=admin_secret_token_123
# Optional: Add your own keys for live AI and PayPal sandbox
# GEMINI_API_KEY=your_gemini_api_key
# PAYPAL_CLIENT_ID=your_sandbox_client_id
# PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
```

### 3. Frontend Setup

```bash
cd ../frontend
npm install
npm run build
```

### 4. Run the Application

```bash
cd ../backend
uvicorn app.main:app --port 8000
```

Open **[http://localhost:8000](http://localhost:8000)** in your browser. The backend serves the compiled frontend automatically.

### 5. Quick Demo Walkthrough

1. Go to the **Demo Controls** tab.
2. Click **"Seed Subscribers"** to generate sample data.
3. Click **"Inject Failed Payment"** to simulate a billing crisis.
4. Switch to the **Cases** tab — a new high-severity case appears.
5. Click the case → review the AI diagnosis → click **"Approve & Execute"**.
6. Check the **Action Log** tab to see the recovered MRR.

---

## 🧪 Running Tests

```bash
cd backend
pytest -v
```

All **60 tests** pass, covering detection rules, webhook verification, AI schema parsing, executor idempotency, and end-to-end recovery flows.

---

## 🏗️ Architecture

```
PayPal Webhooks & Subscriptions API
            │
            ▼
┌─────────────────────────────────────────────────┐
│              SALVAGE AI BACKEND                  │
│                                                  │
│  Deterministic     Google Gemini     Human-in-   │
│  Detection ────►   2.5 Flash     ──► the-Loop    │
│  Rules R1–R5       (Read-Only)       Approval    │
│                                         │        │
│  Immutable    ◄── Idempotent  ◄─────────┘        │
│  Audit Log        Executor                       │
└─────────────────────────────────────────────────┘
```

### Key Invariants
- **Read-only AI:** Gemini has zero write access to PayPal or databases.
- **Human approval required:** No payment mutation runs without explicit merchant sign-off.
- **Sandbox-only:** Live PayPal endpoints are blocked unless `ALLOW_LIVE=true`.
- **Deterministic detection:** Rules R1–R5 are pure Python code, not LLM guesses.

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, FastAPI, SQLAlchemy 2.0, SQLite (WAL) |
| **AI Engine** | Google Gemini 2.5 Flash (`google-genai` SDK) |
| **ML Model** | Scikit-Learn (churn prediction) |
| **Frontend** | React 19, TypeScript, Tailwind CSS, Vite |
| **PayPal APIs** | Subscriptions, Webhooks, Transaction Search, OAuth 2.0 |
| **Deployment** | Docker, Render |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
