"""Tests for the executor service."""
from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.db.models import ActionLog, Case, Proposal, Subscription
from app.executor.service import ExecutorError, execute_proposal


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_case_and_proposal(
    db: Session,
    active_subscription: Subscription,
    action_type: str = "RETRY_PAYMENT",
    status: str = "approved",
    proposal_status: str = "approved",
) -> tuple[Case, Proposal]:
    case = Case(
        subscription_id=active_subscription.id,
        type="FAILED_PAYMENT",
        status="proposed",
        severity=80,
        mrr_at_risk=Decimal("29.99"),
        evidence_json="{}",
        opened_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(case)
    db.flush()

    proposal = Proposal(
        case_id=case.id,
        diagnosis="Test diagnosis",
        reasoning="Test reasoning",
        action_type=action_type,
        params_json=json.dumps({}),
        customer_message="",
        confidence=0.85,
        model="claude-test",
        status=proposal_status,
    )
    db.add(proposal)
    db.flush()
    return case, proposal


class TestExecutorGuardrails:
    def test_refuses_unapproved_proposal(
        self, db: Session, active_subscription: Subscription
    ):
        _, proposal = _make_case_and_proposal(
            db, active_subscription, proposal_status="pending"
        )
        with pytest.raises(ExecutorError, match="not approved"):
            execute_proposal(db, proposal.id)

    def test_refuses_dismissed_proposal(
        self, db: Session, active_subscription: Subscription
    ):
        _, proposal = _make_case_and_proposal(
            db, active_subscription, proposal_status="dismissed"
        )
        with pytest.raises(ExecutorError, match="not approved"):
            execute_proposal(db, proposal.id)

    def test_refuses_when_executor_disabled(
        self, db: Session, active_subscription: Subscription
    ):
        _, proposal = _make_case_and_proposal(db, active_subscription)
        with patch("app.executor.service.settings") as mock_settings:
            mock_settings.executor_enabled = False
            with pytest.raises(ExecutorError, match="disabled"):
                execute_proposal(db, proposal.id)

    def test_raises_on_nonexistent_proposal(self, db: Session):
        with pytest.raises(ExecutorError, match="not found"):
            execute_proposal(db, "nonexistent-id-0000")


class TestExecutorIdempotency:
    def test_idempotent_advisory_action(
        self, db: Session, active_subscription: Subscription
    ):
        """Calling execute twice on an advisory action returns existing log."""
        _, proposal = _make_case_and_proposal(
            db, active_subscription, action_type="SEND_DUNNING_MESSAGE"
        )

        log1 = execute_proposal(db, proposal.id)
        log2 = execute_proposal(db, proposal.id)

        assert log1.id == log2.id
        assert log1.success is True

    def test_advisory_action_no_paypal_call(
        self, db: Session, active_subscription: Subscription
    ):
        """Advisory actions should NOT call PayPal APIs."""
        _, proposal = _make_case_and_proposal(
            db, active_subscription, action_type="WIN_BACK_OFFER"
        )

        with patch("app.paypal.client.capture_subscription_payment") as mock_pp:
            execute_proposal(db, proposal.id)
            mock_pp.assert_not_called()

    def test_action_log_written(
        self, db: Session, active_subscription: Subscription
    ):
        _, proposal = _make_case_and_proposal(
            db, active_subscription, action_type="NO_ACTION"
        )

        log = execute_proposal(db, proposal.id)
        assert db.query(ActionLog).filter_by(proposal_id=proposal.id).count() == 1
        assert log.success is True

    def test_case_resolved_after_success(
        self, db: Session, active_subscription: Subscription
    ):
        case, proposal = _make_case_and_proposal(
            db, active_subscription, action_type="NO_ACTION"
        )

        execute_proposal(db, proposal.id)
        db.refresh(case)
        assert case.status == "resolved"


class TestExecutorPayPalActions:
    def test_retry_payment_calls_paypal(
        self, db: Session, active_subscription: Subscription
    ):
        _, proposal = _make_case_and_proposal(
            db, active_subscription, action_type="RETRY_PAYMENT"
        )

        with patch("app.executor.service._execute_retry_payment") as mock_retry:
            mock_retry.return_value = None
            execute_proposal(db, proposal.id)
            mock_retry.assert_called_once()

    def test_reactivate_calls_paypal(
        self, db: Session, active_subscription: Subscription
    ):
        _, proposal = _make_case_and_proposal(
            db, active_subscription, action_type="REACTIVATE_SUBSCRIPTION"
        )

        with patch("app.executor.service._execute_reactivate") as mock_reactivate:
            mock_reactivate.return_value = None
            execute_proposal(db, proposal.id)
            mock_reactivate.assert_called_once()

