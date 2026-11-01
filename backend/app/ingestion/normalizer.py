"""Normalize PayPal API payloads into local DB records."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Payment, Plan, Subscriber, Subscription, WebhookEvent
from app.paypal.schemas import (
    PayPalPlan,
    PayPalSubscription,
    PayPalWebhookEvent,
    TransactionRecord,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

def upsert_plan(db: Session, pp_plan: PayPalPlan) -> Plan:
    """Insert or update a Plan row from a PayPal plan object."""
    existing = db.query(Plan).filter_by(paypal_plan_id=pp_plan.id).first()

    # Extract price and interval from billing_cycles
    price = Decimal("0")
    interval = "MONTH"
    for cycle in pp_plan.billing_cycles:
        if cycle.tenure_type == "REGULAR":
            ps = cycle.pricing_scheme or {}
            if isinstance(ps, dict):
                fixed = ps.get("fixed_price") or ps.get("pricing_model") or {}
                if isinstance(fixed, dict):
                    raw_value = fixed.get("value", "0")
                    price = Decimal(str(raw_value))
            freq = cycle.frequency or {}
            if isinstance(freq, dict):
                interval_unit = freq.get("interval_unit", "MONTH").upper()
                interval = interval_unit
            break

    if existing:
        existing.name = pp_plan.name
        existing.interval = interval
        existing.price = price
        existing.active = pp_plan.status == "ACTIVE"
        db.flush()
        return existing

    plan = Plan(
        paypal_plan_id=pp_plan.id,
        name=pp_plan.name,
        interval=interval,
        price=price,
        currency="USD",
        active=pp_plan.status == "ACTIVE",
    )
    db.add(plan)
    db.flush()
    return plan


# ---------------------------------------------------------------------------
# Subscriber
# ---------------------------------------------------------------------------

def upsert_subscriber(
    db: Session,
    paypal_payer_id: Optional[str],
    email: str,
    name: str = "",
    source: str = "real",
) -> Subscriber:
    """Insert or update a Subscriber row."""
    if paypal_payer_id:
        existing = db.query(Subscriber).filter_by(paypal_payer_id=paypal_payer_id).first()
    else:
        existing = db.query(Subscriber).filter_by(email=email).first()

    if existing:
        existing.email = email or existing.email
        existing.name = name or existing.name
        db.flush()
        return existing

    subscriber = Subscriber(
        paypal_payer_id=paypal_payer_id,
        email=email,
        name=name,
        source=source,
    )
    db.add(subscriber)
    db.flush()
    return subscriber


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

def upsert_subscription(
    db: Session,
    pp_sub: PayPalSubscription,
    plan: Plan,
    subscriber: Subscriber,
    source: str = "real",
) -> Subscription:
    """Insert or update a Subscription row."""
    existing = (
        db.query(Subscription).filter_by(paypal_subscription_id=pp_sub.id).first()
    )

    start_time = _ensure_utc(pp_sub.start_time) or _ensure_utc(pp_sub.create_time) or _utcnow()

    # Map status to local values
    status = pp_sub.status  # keep PayPal status strings

    if existing:
        existing.status = status
        existing.plan_id = plan.id
        # Update suspension / cancellation timestamps
        if status == "SUSPENDED" and not existing.suspended_at:
            existing.suspended_at = _utcnow()
        elif status == "CANCELLED" and not existing.cancelled_at:
            existing.cancelled_at = _utcnow()
        elif status == "ACTIVE":
            existing.suspended_at = None
        db.flush()
        return existing

    subscription = Subscription(
        paypal_subscription_id=pp_sub.id,
        subscriber_id=subscriber.id,
        plan_id=plan.id,
        status=status,
        start_time=start_time,
        source=source,
    )
    db.add(subscription)
    db.flush()
    return subscription


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

def upsert_payment(
    db: Session,
    subscription: Subscription,
    txn: TransactionRecord,
    source: str = "real",
) -> Optional[Payment]:
    """Insert or update a Payment row from a transaction record."""
    ti = txn.transaction_info
    txn_id = ti.transaction_id
    if not txn_id:
        return None

    existing = db.query(Payment).filter_by(paypal_txn_id=txn_id).first()

    raw_amount = Decimal("0")
    currency = "USD"
    if ti.transaction_amount:
        raw_amount = Decimal(str(ti.transaction_amount.value))
        currency = ti.transaction_amount.currency_code

    status = ti.transaction_status or "UNKNOWN"
    occurred_at = _ensure_utc(ti.transaction_initiation_date) or _utcnow()

    if existing:
        existing.status = status
        existing.amount = raw_amount
        existing.occurred_at = occurred_at
        db.flush()
        return existing

    payment = Payment(
        paypal_txn_id=txn_id,
        subscription_id=subscription.id,
        amount=raw_amount,
        currency=currency,
        status=status,
        occurred_at=occurred_at,
        source=source,
    )
    db.add(payment)
    db.flush()
    return payment


# ---------------------------------------------------------------------------
# Webhook event
# ---------------------------------------------------------------------------

def record_webhook_event(
    db: Session,
    event: PayPalWebhookEvent,
    raw_body: bytes,
    verified: bool,
) -> tuple[WebhookEvent, bool]:
    """
    Persist a webhook event. Returns (row, is_new).
    is_new=False means it was a duplicate — caller should skip processing.
    """
    existing = db.query(WebhookEvent).filter_by(paypal_event_id=event.id).first()
    if existing:
        return existing, False

    row = WebhookEvent(
        paypal_event_id=event.id,
        event_type=event.event_type,
        payload_json=raw_body.decode("utf-8", errors="replace"),
        verified=verified,
    )
    db.add(row)
    db.flush()
    return row, True

