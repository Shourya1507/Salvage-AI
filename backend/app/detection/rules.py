"""Detection rules R1-R5 for revenue leak identification."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Case, Payment, Plan, Subscription
from app.detection.severity import (
    compute_severity,
    normalize_mrr,
    urgency_from_amount,
    urgency_from_churn_score,
    urgency_from_days,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _open_case(
    db: Session,
    subscription_id: str,
    case_type: str,
    severity: int,
    mrr_at_risk: Decimal,
    evidence: dict,
) -> Optional[Case]:
    """Create a case if one of the same type isn't already open for this subscription."""
    existing = (
        db.query(Case)
        .filter_by(subscription_id=subscription_id, type=case_type)
        .filter(Case.status.in_(["open", "proposed"]))
        .first()
    )
    if existing:
        # Update severity / MRR if changed
        existing.severity = max(existing.severity, severity)
        existing.mrr_at_risk = max(existing.mrr_at_risk, mrr_at_risk)
        existing.updated_at = _utcnow()
        db.flush()
        return existing

    case = Case(
        subscription_id=subscription_id,
        type=case_type,
        severity=severity,
        mrr_at_risk=mrr_at_risk,
        evidence_json=json.dumps(evidence),
        opened_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(case)
    db.flush()
    return case


def _get_mrr(subscription: Subscription) -> Decimal:
    plan: Plan = subscription.plan
    return normalize_mrr(plan.price, plan.interval)


# ---------------------------------------------------------------------------
# R1: Failed payment
# ---------------------------------------------------------------------------

def detect_r1_failed_payment(db: Session) -> list[Case]:
    """
    R1: Subscriptions in SUSPENDED state (payment failure) or
        subscriptions with recent FAILED payment events.
    """
    cases: list[Case] = []

    # Subscriptions in failure-related states
    failed_subs = (
        db.query(Subscription)
        .filter(Subscription.status.in_(["SUSPENDED", "PAYMENT_FAILURE"]))
        .all()
    )

    for sub in failed_subs:
        mrr = _get_mrr(sub)
        days_since = 0.0
        if sub.suspended_at:
            days_since = ((_utcnow() - sub.suspended_at).total_seconds() / 86400)
        urgency = urgency_from_days(days_since, max_days=14)
        severity = compute_severity(mrr, urgency)

        evidence = {
            "rule": "R1",
            "subscription_status": sub.status,
            "suspended_at": sub.suspended_at.isoformat() if sub.suspended_at else None,
            "days_since_suspension": round(days_since, 1),
            "paypal_subscription_id": sub.paypal_subscription_id,
        }
        case = _open_case(db, sub.id, "FAILED_PAYMENT", severity, mrr, evidence)
        if case:
            cases.append(case)

    # Recent failed payments in the DB
    cutoff = _utcnow() - timedelta(days=30)
    failed_payments = (
        db.query(Payment)
        .filter(
            Payment.status.in_(["FAILED", "DENIED", "REVERSED", "PENDING"]),
            Payment.occurred_at >= cutoff,
        )
        .all()
    )

    seen_sub_ids = {sub.id for sub in failed_subs}
    for payment in failed_payments:
        if payment.subscription_id in seen_sub_ids:
            continue
        seen_sub_ids.add(payment.subscription_id)

        sub = db.get(Subscription, payment.subscription_id)
        if not sub:
            continue

        mrr = _get_mrr(sub)
        days_since = (_utcnow() - payment.occurred_at).total_seconds() / 86400
        urgency = urgency_from_days(days_since, max_days=14)
        severity = compute_severity(mrr, urgency)

        evidence = {
            "rule": "R1",
            "trigger": "failed_payment",
            "payment_id": payment.id,
            "paypal_txn_id": payment.paypal_txn_id,
            "payment_status": payment.status,
            "payment_amount": str(payment.amount),
            "occurred_at": payment.occurred_at.isoformat(),
        }
        case = _open_case(db, sub.id, "FAILED_PAYMENT", severity, mrr, evidence)
        if case:
            cases.append(case)

    db.flush()
    return cases


# ---------------------------------------------------------------------------
# R2: Stalled suspension
# ---------------------------------------------------------------------------

def detect_r2_stalled_suspension(db: Session) -> list[Case]:
    """
    R2: Subscriptions that have been SUSPENDED for more than STALLED_DAYS days.
    """
    threshold_dt = _utcnow() - timedelta(days=settings.stalled_days)

    stalled = (
        db.query(Subscription)
        .filter(
            Subscription.status == "SUSPENDED",
            Subscription.suspended_at <= threshold_dt,
            Subscription.suspended_at.isnot(None),
        )
        .all()
    )

    cases: list[Case] = []
    for sub in stalled:
        mrr = _get_mrr(sub)
        days_stalled = (_utcnow() - sub.suspended_at).total_seconds() / 86400  # type: ignore[operator]
        urgency = urgency_from_days(days_stalled, max_days=60)
        severity = compute_severity(mrr, urgency)

        evidence = {
            "rule": "R2",
            "suspended_at": sub.suspended_at.isoformat(),  # type: ignore[union-attr]
            "days_stalled": round(days_stalled, 1),
            "paypal_subscription_id": sub.paypal_subscription_id,
        }
        case = _open_case(db, sub.id, "STALLED_SUSPENSION", severity, mrr, evidence)
        if case:
            cases.append(case)

    db.flush()
    return cases


# ---------------------------------------------------------------------------
# R3: Duplicate charge
# ---------------------------------------------------------------------------

def detect_r3_duplicate_charge(db: Session) -> list[Case]:
    """
    R3: Same subscriber, same amount, different txn IDs, within DUPLICATE_WINDOW_HOURS.
    """
    window = timedelta(hours=settings.duplicate_window_hours)
    cutoff = _utcnow() - window

    recent_payments = (
        db.query(Payment)
        .filter(Payment.occurred_at >= cutoff, Payment.status == "COMPLETED")
        .all()
    )

    # Group by (subscriber_id, amount)
    from collections import defaultdict

    groups: dict[tuple[str, Decimal], list[Payment]] = defaultdict(list)
    for p in recent_payments:
        sub = db.get(Subscription, p.subscription_id)
        if not sub:
            continue
        key = (sub.subscriber_id, p.amount)
        groups[key].append(p)

    cases: list[Case] = []
    seen_subs: set[str] = set()
    for (subscriber_id, amount), payments in groups.items():
        if len(payments) < 2:
            continue
        # Check they span different subscriptions or different txn IDs
        txn_ids = {p.paypal_txn_id for p in payments if p.paypal_txn_id}
        if len(txn_ids) < 2:
            continue

        # Use first payment's subscription
        first = payments[0]
        if first.subscription_id in seen_subs:
            continue
        seen_subs.add(first.subscription_id)

        sub = db.get(Subscription, first.subscription_id)
        if not sub:
            continue

        mrr = _get_mrr(sub)
        urgency = urgency_from_amount(amount)
        severity = compute_severity(amount, urgency)  # severity driven by amount

        evidence = {
            "rule": "R3",
            "subscriber_id": subscriber_id,
            "amount": str(amount),
            "txn_ids": list(txn_ids),
            "payment_count": len(payments),
            "window_hours": settings.duplicate_window_hours,
        }
        case = _open_case(db, sub.id, "DUPLICATE", severity, mrr, evidence)
        if case:
            cases.append(case)

    db.flush()
    return cases


# ---------------------------------------------------------------------------
# R4: Price-change fallout
# ---------------------------------------------------------------------------

def detect_r4_price_fallout(db: Session) -> list[Case]:
    """
    R4: Detect plans where cancellation/failure rate rose after price changes.
    This is a heuristic: compare plan price to subscriptions' payment failure rate.
    Since PayPal sandbox doesn't expose price-change history, we detect if a plan
    has a high failure ratio among its subscriptions.
    """
    plans = db.query(Plan).filter_by(active=True).all()
    cases: list[Case] = []

    for plan in plans:
        subs = (
            db.query(Subscription).filter_by(plan_id=plan.id).all()
        )
        if len(subs) < 3:
            continue

        cancelled_or_failed = sum(
            1 for s in subs if s.status in ("CANCELLED", "SUSPENDED", "PAYMENT_FAILURE")
        )
        failure_rate = cancelled_or_failed / len(subs)

        # Threshold: flag if >30% of cohort is cancelled/failed
        if failure_rate < 0.30:
            continue

        cohort_mrr = normalize_mrr(plan.price, plan.interval) * Decimal(len(subs))
        urgency = min(failure_rate * 2, 1.0)  # scale: 50% failure → urgency=1.0
        severity = compute_severity(cohort_mrr, urgency)

        # Use the most recently-failing subscription as the anchor
        anchor_sub = next(
            (s for s in subs if s.status in ("CANCELLED", "SUSPENDED")), subs[0]
        )

        evidence = {
            "rule": "R4",
            "plan_id": plan.id,
            "paypal_plan_id": plan.paypal_plan_id,
            "plan_name": plan.name,
            "plan_price": str(plan.price),
            "plan_interval": plan.interval,
            "total_subs": len(subs),
            "cancelled_or_failed": cancelled_or_failed,
            "failure_rate": round(failure_rate, 3),
        }
        case = _open_case(db, anchor_sub.id, "PRICE_FALLOUT", severity, cohort_mrr, evidence)
        if case:
            cases.append(case)

    db.flush()
    return cases


# ---------------------------------------------------------------------------
# R5: At-risk subscriber (churn score)
# ---------------------------------------------------------------------------

def detect_r5_at_risk(db: Session) -> list[Case]:
    """
    R5: Subscriptions with a churn score >= CHURN_THRESHOLD.
    """
    from app.db.models import ChurnScore

    threshold = settings.churn_threshold
    # Get latest churn score per subscription
    from sqlalchemy import func as sqlfunc

    latest_scores = (
        db.query(
            ChurnScore.subscription_id,
            sqlfunc.max(ChurnScore.scored_at).label("latest_at"),
        )
        .group_by(ChurnScore.subscription_id)
        .subquery()
    )

    at_risk = (
        db.query(ChurnScore)
        .join(
            latest_scores,
            (ChurnScore.subscription_id == latest_scores.c.subscription_id)
            & (ChurnScore.scored_at == latest_scores.c.latest_at),
        )
        .filter(ChurnScore.score >= threshold)
        .all()
    )

    cases: list[Case] = []
    for score_row in at_risk:
        sub = db.get(Subscription, score_row.subscription_id)
        if not sub or sub.status not in ("ACTIVE",):
            continue

        mrr = _get_mrr(sub)
        urgency = urgency_from_churn_score(float(score_row.score))
        mrr_at_risk = mrr * Decimal(str(score_row.score))
        severity = compute_severity(mrr_at_risk, urgency)

        evidence = {
            "rule": "R5",
            "churn_score": float(score_row.score),
            "threshold": threshold,
            "model_version": score_row.model_version,
            "features": json.loads(score_row.features_json),
            "scored_at": score_row.scored_at.isoformat(),
        }
        case = _open_case(db, sub.id, "AT_RISK", severity, mrr_at_risk, evidence)
        if case:
            cases.append(case)

    db.flush()
    return cases


# ---------------------------------------------------------------------------
# Run all rules
# ---------------------------------------------------------------------------

def run_all_rules(db: Session) -> dict[str, int]:
    """Execute all detection rules. Returns a dict of rule → case count."""
    counts = {}
    counts["R1"] = len(detect_r1_failed_payment(db))
    counts["R2"] = len(detect_r2_stalled_suspension(db))
    counts["R3"] = len(detect_r3_duplicate_charge(db))
    counts["R4"] = len(detect_r4_price_fallout(db))
    counts["R5"] = len(detect_r5_at_risk(db))
    db.commit()
    logger.info("Detection run complete: %s", counts)
    return counts

