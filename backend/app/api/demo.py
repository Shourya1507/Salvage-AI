"""Demo router: POST /api/demo/seed|inject|reset (DEMO_MODE only)"""
from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    Case,
    ChurnScore,
    Payment,
    Plan,
    Proposal,
    Subscriber,
    Subscription,
    WebhookEvent,
    ActionLog,
)
from app.db.session import get_db
from app.detection.rules import run_all_rules

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/demo", tags=["demo"])


def _require_demo_mode() -> None:
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode is disabled")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _randdt(days_ago_min: int = 1, days_ago_max: int = 90) -> datetime:
    delta = random.randint(days_ago_min * 86400, days_ago_max * 86400)
    return _utcnow() - timedelta(seconds=delta)


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

class SeedRequest(BaseModel):
    subscriber_count: int = 10
    plan_count: int = 2


@router.post("/seed")
def seed_demo(
    body: SeedRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_demo_mode),
) -> dict:
    """Seed the database with simulated plans, subscribers, and subscriptions."""

    plan_count = max(1, min(body.plan_count, 5))
    subscriber_count = max(1, min(body.subscriber_count, 100))

    # Create plans
    plans: list[Plan] = []
    for i in range(plan_count):
        interval = "MONTH" if i % 2 == 0 else "YEAR"
        price = Decimal(str(round(random.uniform(9.99, 99.99), 2)))
        plan = Plan(
            paypal_plan_id=f"DEMO-PLAN-{uuid.uuid4().hex[:8].upper()}",
            name=f"Demo Plan {i + 1} ({interval})",
            interval=interval,
            price=price,
            currency="USD",
            active=True,
        )
        db.add(plan)
        plans.append(plan)

    db.flush()

    # Create subscribers and subscriptions
    statuses = ["ACTIVE", "ACTIVE", "ACTIVE", "SUSPENDED", "CANCELLED"]
    created_subs: list[Subscription] = []

    for i in range(subscriber_count):
        subscriber = Subscriber(
            email=f"demo_user_{i}_{uuid.uuid4().hex[:6]}@example.com",
            name=f"Demo User {i}",
            source="simulated",
        )
        db.add(subscriber)
        db.flush()

        plan = random.choice(plans)
        status = random.choice(statuses)
        start = _randdt(30, 365)
        suspended_at = None
        cancelled_at = None

        if status == "SUSPENDED":
            suspended_at = _randdt(1, 30)
        elif status == "CANCELLED":
            cancelled_at = _randdt(1, 60)

        sub = Subscription(
            paypal_subscription_id=f"I-DEMO-{uuid.uuid4().hex[:12].upper()}",
            subscriber_id=subscriber.id,
            plan_id=plan.id,
            status=status,
            start_time=start,
            suspended_at=suspended_at,
            cancelled_at=cancelled_at,
            source="simulated",
        )
        db.add(sub)
        db.flush()
        created_subs.append(sub)

        # Add some payments
        payment_count = random.randint(1, 6)
        for j in range(payment_count):
            pstatus = random.choice(["COMPLETED", "COMPLETED", "COMPLETED", "FAILED"])
            occurred = start + timedelta(days=30 * j)
            if occurred > _utcnow():
                break
            payment = Payment(
                paypal_txn_id=f"DEMO-TXN-{uuid.uuid4().hex[:12].upper()}",
                subscription_id=sub.id,
                amount=plan.price,
                currency="USD",
                status=pstatus,
                occurred_at=occurred,
                source="simulated",
            )
            db.add(payment)

        # Add churn score
        score = round(random.uniform(0.1, 0.95), 4)
        cs = ChurnScore(
            subscription_id=sub.id,
            score=score,
            features_json=json.dumps({"tenure_months": random.randint(1, 24), "monthly_charge": float(plan.price)}),
            model_version="v1.0-demo",
        )
        db.add(cs)

    db.flush()

    # Run detection rules
    try:
        counts = run_all_rules(db)
    except Exception as exc:
        logger.warning("Detection rules failed during seed: %s", exc)
        counts = {}

    db.commit()

    return {
        "status": "seeded",
        "plans": len(plans),
        "subscribers": subscriber_count,
        "subscriptions": len(created_subs),
        "cases_created": counts,
    }


# ---------------------------------------------------------------------------
# Inject
# ---------------------------------------------------------------------------

class InjectRequest(BaseModel):
    event_type: str = "BILLING.SUBSCRIPTION.PAYMENT.FAILED"
    subscription_id: Optional[str] = None  # local sub ID; if None, picks random


@router.post("/inject")
def inject_event(
    body: InjectRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_demo_mode),
) -> dict:
    """Inject a simulated PayPal webhook event."""

    if body.subscription_id:
        sub = db.query(Subscription).get(body.subscription_id)
    else:
        sub = (
            db.query(Subscription)
            .filter_by(source="simulated", status="ACTIVE")
            .order_by(Subscription.start_time.desc())
            .first()
        )

    if not sub:
        raise HTTPException(status_code=404, detail="No suitable subscription found to inject event")

    fake_event_id = f"DEMO-EVT-{uuid.uuid4().hex.upper()}"
    payload: dict[str, Any] = {
        "id": fake_event_id,
        "event_type": body.event_type,
        "resource_type": "subscription",
        "create_time": _utcnow().isoformat(),
        "resource": {
            "id": sub.paypal_subscription_id or sub.id,
            "plan_id": sub.plan.paypal_plan_id if sub.plan else None,
            "status": "SUSPENDED",
        },
    }

    raw = json.dumps(payload).encode()
    from app.paypal.schemas import PayPalWebhookEvent
    from app.ingestion.normalizer import record_webhook_event

    event_obj = PayPalWebhookEvent.model_validate(payload)
    event_row, is_new = record_webhook_event(db, event_obj, raw, verified=False)

    if is_new:
        # Update subscription state
        if body.event_type in (
            "BILLING.SUBSCRIPTION.PAYMENT.FAILED",
            "BILLING.SUBSCRIPTION.SUSPENDED",
        ):
            sub.status = "SUSPENDED"
            if sub.suspended_at is None:
                sub.suspended_at = _utcnow()
        elif body.event_type == "BILLING.SUBSCRIPTION.CANCELLED":
            sub.status = "CANCELLED"
            if sub.cancelled_at is None:
                sub.cancelled_at = _utcnow()

        event_row.processed_at = _utcnow()
        db.flush()

        # Re-run detection
        try:
            run_all_rules(db)
        except Exception as exc:
            logger.warning("Detection failed after inject: %s", exc)

    db.commit()

    return {
        "status": "injected",
        "event_id": fake_event_id,
        "event_type": body.event_type,
        "subscription_id": sub.id,
        "is_new": is_new,
    }


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

@router.post("/reset")
def reset_demo(
    db: Session = Depends(get_db),
    _: None = Depends(_require_demo_mode),
) -> dict:
    """Delete all simulated data from the database."""
    # Delete in dependency order
    # ActionLog references Proposals; Proposals reference Cases; Cases reference Subscriptions
    # We filter by source=simulated where possible

    simulated_sub_ids = [
        r.id for r in db.query(Subscription.id).filter_by(source="simulated").all()
    ]

    if simulated_sub_ids:
        # ChurnScores
        db.query(ChurnScore).filter(ChurnScore.subscription_id.in_(simulated_sub_ids)).delete(synchronize_session=False)

        # Payments
        db.query(Payment).filter(
            Payment.subscription_id.in_(simulated_sub_ids), Payment.source == "simulated"
        ).delete(synchronize_session=False)

        # Cases + Proposals + ActionLogs
        case_ids = [
            r.id for r in db.query(Case.id).filter(Case.subscription_id.in_(simulated_sub_ids)).all()
        ]
        if case_ids:
            proposal_ids = [
                r.id for r in db.query(Proposal.id).filter(Proposal.case_id.in_(case_ids)).all()
            ]
            if proposal_ids:
                db.query(ActionLog).filter(ActionLog.proposal_id.in_(proposal_ids)).delete(synchronize_session=False)
            db.query(Proposal).filter(Proposal.case_id.in_(case_ids)).delete(synchronize_session=False)
        db.query(Case).filter(Case.subscription_id.in_(simulated_sub_ids)).delete(synchronize_session=False)

        # Subscriptions
        db.query(Subscription).filter(Subscription.id.in_(simulated_sub_ids)).delete(synchronize_session=False)

    # Subscribers
    db.query(Subscriber).filter_by(source="simulated").delete(synchronize_session=False)

    # Plans (demo plans start with DEMO-)
    db.query(Plan).filter(Plan.paypal_plan_id.like("DEMO-%")).delete(synchronize_session=False)

    # Demo webhook events
    db.query(WebhookEvent).filter(WebhookEvent.paypal_event_id.like("DEMO-%")).delete(synchronize_session=False)

    db.commit()

    return {"status": "reset", "message": "All simulated data deleted"}

