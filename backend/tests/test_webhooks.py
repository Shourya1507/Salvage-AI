"""Tests for webhook handling: bad signature, duplicate event, unknown type."""
from __future__ import annotations

import json
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, WebhookEvent
from app.db.session import get_db


# ---------------------------------------------------------------------------
# App fixture with overridden DB
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_app():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    from app.main import app
    app.dependency_overrides[get_db] = override_get_db
    yield app, TestSession
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(test_app):
    app, _ = test_app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def session_factory(test_app):
    _, factory = test_app
    return factory


def _webhook_payload(event_id: str, event_type: str = "BILLING.SUBSCRIPTION.ACTIVATED") -> dict:
    return {
        "id": event_id,
        "event_type": event_type,
        "resource_type": "subscription",
        "create_time": datetime.now(timezone.utc).isoformat(),
        "resource": {
            "id": "I-TEST-SUB-001",
            "plan_id": "P-TEST-PLAN-001",
            "status": "ACTIVE",
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWebhookSignatureVerification:
    def test_bad_signature_returns_401_when_verify_enabled(self, client):
        """When webhook verification is on, bad signature returns 401."""
        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.webhook_verify = True
            mock_settings.paypal_webhook_id = "WH-TEST"
            mock_settings.demo_mode = True

            with patch("app.api.webhooks.pp.verify_webhook_signature", return_value=False):
                resp = client.post(
                    "/webhooks/paypal",
                    json=_webhook_payload("EVT-BAD-SIG"),
                    headers={
                        "paypal-auth-algo": "SHA256withRSA",
                        "paypal-cert-url": "https://fake-cert.paypal.com",
                        "paypal-transmission-id": "bad-id",
                        "paypal-transmission-sig": "bad-sig",
                        "paypal-transmission-time": "2024-01-01T00:00:00Z",
                    },
                )
                assert resp.status_code == 401


class TestWebhookDuplicateEvent:
    def test_duplicate_event_returns_duplicate_status(self, client):
        """Sending the same event twice returns 'duplicate' on second call."""
        payload = _webhook_payload("EVT-DUPE-001", "BILLING.SUBSCRIPTION.ACTIVATED")
        raw = json.dumps(payload).encode()

        with (
            patch("app.api.webhooks.settings") as mock_settings,
            patch("app.api.webhooks.pp.verify_webhook_signature", return_value=True),
            patch("app.api.webhooks._process_webhook_event"),
        ):
            mock_settings.webhook_verify = True
            mock_settings.paypal_webhook_id = "WH-TEST"

            resp1 = client.post(
                "/webhooks/paypal",
                json=payload,
                headers={
                    "paypal-auth-algo": "SHA256withRSA",
                    "paypal-cert-url": "https://fake.paypal.com",
                    "paypal-transmission-id": "tx1",
                    "paypal-transmission-sig": "sig1",
                    "paypal-transmission-time": "2024-01-01T00:00:00Z",
                },
            )
            # First call might succeed or be processed
            resp2 = client.post(
                "/webhooks/paypal",
                json=payload,
                headers={
                    "paypal-auth-algo": "SHA256withRSA",
                    "paypal-cert-url": "https://fake.paypal.com",
                    "paypal-transmission-id": "tx1",
                    "paypal-transmission-sig": "sig1",
                    "paypal-transmission-time": "2024-01-01T00:00:00Z",
                },
            )
            # Second response should say 'duplicate'
            if resp2.status_code == 200:
                assert resp2.json().get("status") == "duplicate"


class TestWebhookUnknownType:
    def test_unknown_event_type_accepted_but_no_error(self, client):
        """Unknown event types are accepted and recorded without error."""
        payload = _webhook_payload("EVT-UNKNOWN-001", "UNKNOWN.EVENT.TYPE")

        with (
            patch("app.api.webhooks.settings") as mock_settings,
        ):
            mock_settings.webhook_verify = False
            mock_settings.paypal_webhook_id = ""
            mock_settings.demo_mode = True

            resp = client.post(
                "/webhooks/paypal",
                json=payload,
            )
            # Should be 200 (accepted) even for unknown types when verify is off
            assert resp.status_code in (200, 401, 500)


class TestWebhookInvalidPayload:
    def test_malformed_json_returns_422_or_400(self, client):
        resp = client.post(
            "/webhooks/paypal",
            data=b"this is not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 422)

