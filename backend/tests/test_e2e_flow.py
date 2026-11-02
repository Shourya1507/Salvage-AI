"""End-to-end integration test verifying complete Salvage AI workflow."""
import os
import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.agent.schemas import AgentOutput, ActionType


def test_full_salvage_lifecycle():
    test_db = "./test_e2e.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    os.environ["PAYPAL_CLIENT_ID"] = "test_id"
    os.environ["PAYPAL_CLIENT_SECRET"] = "test_sec"
    os.environ["LLM_API_KEY"] = "test_key"
    os.environ["ADMIN_TOKEN"] = "admin_secret_token_123"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["DEMO_MODE"] = "true"
    os.environ["WEBHOOK_VERIFY"] = "false"

    # Reset session engine to use the new database url
    from app.config import get_settings
    get_settings.cache_clear()
    import app.db.session as dbsession
    from sqlalchemy import create_engine
    dbsession.engine = create_engine(f"sqlite:///{test_db}", connect_args={"check_same_thread": False})
    dbsession.SessionLocal.configure(bind=dbsession.engine)
    dbsession.init_db()

    from app.main import app

    try:
        with TestClient(app) as client:
            # 1. Seed demo data
            res = client.post("/api/demo/seed", json={"subscribers": 10, "active_ratio": 0.8})
            assert res.status_code == 200, res.text
            seed_data = res.json()
            assert seed_data["subscribers"] == 10

            # 2. Inject failed payment scenario
            res = client.post("/api/demo/inject", json={"event_type": "BILLING.SUBSCRIPTION.PAYMENT.FAILED"})
            assert res.status_code == 200, res.text

            # 3. Fetch open cases
            res = client.get("/api/cases")
            cases_data = res.json()
            cases = cases_data["cases"]
            assert len(cases) > 0, "No cases created after failed payment event!"
            failed_cases = [c for c in cases if c["type"] == "FAILED_PAYMENT"]
            assert len(failed_cases) > 0, "No FAILED_PAYMENT case found!"
            target_case = failed_cases[0]
            assert target_case["status"] in ("open", "proposed")

            # 4. Run diagnosis agent
            mock_output = AgentOutput(
                diagnosis="Subscription renewal failed due to temporary card processing issue.",
                reasoning="Subscriber has 6 months of consecutive successful payments; high retention likelihood.",
                action_type=ActionType.RETRY_PAYMENT,
                params={"retry_attempt": 1},
                confidence=0.92,
                customer_message="Hi, we noticed an issue renewing your subscription. Please update your payment method.",
            )

            with patch("app.agent.runner.run_agent", return_value=mock_output):
                res = client.post(f"/api/cases/{target_case['id']}/run-agent")
                assert res.status_code == 200, res.text
                proposal = res.json()
                assert proposal["action_type"] == "RETRY_PAYMENT"
                assert proposal["status"] == "pending"

            # 5. Approve proposal (Human-in-the-loop)
            from app.config import settings as app_settings
            headers = {"x-admin-token": app_settings.admin_token}
            with patch(
                "app.paypal.client.capture_subscription_payment",
                return_value={"status": "COMPLETED"},
            ):
                res = client.post(
                    f"/api/proposals/{proposal['proposal_id']}/approve",
                    json={},
                    headers=headers,
                )
                assert res.status_code == 200, res.text
                exec_res = res.json()
                assert exec_res["success"] is True

            # 6. Verify case is resolved and includes subscriber/plan/subscription details
            res = client.get(f"/api/cases/{target_case['id']}")
            case_detail = res.json()
            assert case_detail["status"] == "resolved"
            assert case_detail["subscriber"] is not None
            assert "email" in case_detail["subscriber"]
            assert case_detail["plan"] is not None
            assert "price" in case_detail["plan"]
            assert case_detail["subscription"] is not None
            assert len(case_detail["proposals"]) > 0
            assert case_detail["proposals"][0]["action_type"] == "RETRY_PAYMENT"

            # 7. Verify dashboard statistics updated
            res = client.get("/api/dashboard")
            dash = res.json()
            assert dash["total_recovered_mrr"] > 0, "Recovered MRR should be positive!"

            # 8. Verify action log
            res = client.get("/api/actions", headers=headers)
            logs_data = res.json()
            logs = logs_data["actions"]
            assert len(logs) > 0
            assert logs[0]["action_type"] == "RETRY_PAYMENT"
            assert logs[0]["success"] is True
    finally:
        dbsession.engine.dispose()
        if os.path.exists(test_db):
            os.remove(test_db)
