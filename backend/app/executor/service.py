"""Executor service: execute approved proposals via PayPal API."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ActionLog, Case, Payment, Proposal, Subscription

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Parameter allow-list per action type
# ---------------------------------------------------------------------------
_ALLOWED_PARAMS: dict[str, set[str]] = {
    "RETRY_PAYMENT": {"note"},
    "REACTIVATE_SUBSCRIPTION": {"reason"},
    "SUSPEND_SUBSCRIPTION": {"reason"},
    "CANCEL_SUBSCRIPTION": {"reason"},
    "SEND_DUNNING_MESSAGE": {"message", "channel"},
    "WIN_BACK_OFFER": {"discount_percent", "message"},
    "REVIEW_DUPLICATE_FOR_REFUND": {"notes"},
    "NO_ACTION": {"reason"},
}

# Advisory actions that require no PayPal API call
_ADVISORY_ACTIONS = {
    "SEND_DUNNING_MESSAGE",
    "WIN_BACK_OFFER",
    "REVIEW_DUPLICATE_FOR_REFUND",
    "NO_ACTION",
}

# Amount cap for retry (USD)
_MAX_RETRY_AMOUNT = Decimal("10000")


class ExecutorError(Exception):
    """Raised when execution cannot proceed."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _filter_params(action_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Strip params not in the allow-list for this action type."""
    allowed = _ALLOWED_PARAMS.get(action_type, set())
    return {k: v for k, v in params.items() if k in allowed}


def execute_proposal(db: Session, proposal_id: str) -> ActionLog:
    """
    Execute an approved proposal.
    - Only executes proposals with status='approved'.
    - Idempotent: raises ExecutorError if already executed successfully.
    - Writes to action_log; updates case and subscription state.

    Returns the ActionLog row.
    Raises ExecutorError on guard failures.
    """
    if not settings.executor_enabled:
        raise ExecutorError("Executor is disabled (EXECUTOR_ENABLED=false)")

    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise ExecutorError(f"Proposal {proposal_id} not found")

    # Check idempotency
    existing_log = (
        db.query(ActionLog)
        .filter_by(proposal_id=proposal_id)
        .filter(ActionLog.success == True)  # noqa: E712
        .first()
    )
    if existing_log:
        logger.info("Proposal %s already successfully executed – skipping", proposal_id)
        return existing_log

    if proposal.status != "approved":
        raise ExecutorError(
            f"Proposal {proposal_id} is not approved (status={proposal.status}). "
            "Only approved proposals can be executed."
        )

    # Resolve case and subscription
    case: Case = proposal.case
    subscription: Subscription = case.subscription

    # Use edited params if provided, otherwise original params
    params_json = proposal.edited_params_json or proposal.params_json
    params: dict[str, Any] = json.loads(params_json or "{}")
    params = _filter_params(proposal.action_type, params)

    request_payload = {
        "action_type": proposal.action_type,
        "proposal_id": proposal_id,
        "subscription_id": subscription.id,
        "paypal_subscription_id": subscription.paypal_subscription_id,
        "params": params,
    }

    response_payload: dict[str, Any] = {}
    success = False
    recovered_mrr: Decimal | None = None

    try:
        if proposal.action_type in _ADVISORY_ACTIONS:
            response_payload = {
                "status": "handled_by_merchant",
                "message": f"Advisory action '{proposal.action_type}' recorded. No PayPal API call made.",
            }
            success = True

        elif proposal.action_type == "RETRY_PAYMENT":
            _execute_retry_payment(subscription, params, response_payload)
            success = True
            # Estimate recovered MRR from plan
            from app.detection.severity import normalize_mrr
            recovered_mrr = normalize_mrr(subscription.plan.price, subscription.plan.interval)

        elif proposal.action_type == "REACTIVATE_SUBSCRIPTION":
            _execute_reactivate(subscription, params, response_payload)
            success = True
            subscription.status = "ACTIVE"
            subscription.suspended_at = None

        elif proposal.action_type == "SUSPEND_SUBSCRIPTION":
            _execute_suspend(subscription, params, response_payload)
            success = True
            subscription.status = "SUSPENDED"
            subscription.suspended_at = _utcnow()

        elif proposal.action_type == "CANCEL_SUBSCRIPTION":
            _execute_cancel(subscription, params, response_payload)
            success = True
            subscription.status = "CANCELLED"
            subscription.cancelled_at = _utcnow()

        else:
            raise ExecutorError(f"Unknown action_type: {proposal.action_type}")

    except ExecutorError:
        raise
    except Exception as exc:
        logger.error("Execution failed for proposal %s: %s", proposal_id, exc)
        response_payload["error"] = str(exc)
        success = False

    # Write action log
    log_entry = ActionLog(
        proposal_id=proposal_id,
        action_type=proposal.action_type,
        request_json=json.dumps(request_payload),
        response_json=json.dumps(response_payload),
        success=success,
        executed_at=_utcnow(),
        recovered_mrr=recovered_mrr,
    )

    try:
        db.add(log_entry)
        db.flush()
    except IntegrityError:
        db.rollback()
        # Another process already inserted – fetch and return existing
        existing = db.query(ActionLog).filter_by(proposal_id=proposal_id).first()
        if existing:
            return existing
        raise

    # Update proposal status
    proposal.status = "executed" if success else "failed"
    proposal.decided_at = _utcnow()

    # Update case status
    if success:
        case.status = "resolved"
        case.updated_at = _utcnow()

    db.commit()
    return log_entry


def _execute_retry_payment(
    subscription: Subscription,
    params: dict[str, Any],
    response: dict[str, Any],
) -> None:
    from app.paypal import client as pp

    paypal_id = subscription.paypal_subscription_id
    if not paypal_id:
        raise ExecutorError("Subscription has no PayPal ID – cannot retry payment")

    note = str(params.get("note", "Salvage AI: retry outstanding payment"))
    result = pp.capture_subscription_payment(paypal_id, note=note)
    response["paypal_response"] = result


def _execute_reactivate(
    subscription: Subscription,
    params: dict[str, Any],
    response: dict[str, Any],
) -> None:
    from app.paypal import client as pp

    paypal_id = subscription.paypal_subscription_id
    if not paypal_id:
        raise ExecutorError("Subscription has no PayPal ID – cannot reactivate")

    reason = str(params.get("reason", "Reactivated by Salvage AI"))
    pp.activate_subscription(paypal_id, reason=reason)
    response["activated"] = True


def _execute_suspend(
    subscription: Subscription,
    params: dict[str, Any],
    response: dict[str, Any],
) -> None:
    from app.paypal import client as pp

    paypal_id = subscription.paypal_subscription_id
    if not paypal_id:
        raise ExecutorError("Subscription has no PayPal ID – cannot suspend")

    reason = str(params.get("reason", "Suspended by Salvage AI"))
    pp.suspend_subscription(paypal_id, reason=reason)
    response["suspended"] = True


def _execute_cancel(
    subscription: Subscription,
    params: dict[str, Any],
    response: dict[str, Any],
) -> None:
    from app.paypal import client as pp

    paypal_id = subscription.paypal_subscription_id
    if not paypal_id:
        raise ExecutorError("Subscription has no PayPal ID – cannot cancel")

    reason = str(params.get("reason", "Cancelled by Salvage AI"))
    pp.cancel_subscription(paypal_id, reason=reason)
    response["cancelled"] = True

