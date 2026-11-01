"""Unit tests for detection rules R1-R5, severity scoring, and MRR normalization."""
from __future__ import annotations

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.db.models import Case, ChurnScore, Payment, Plan, Subscriber, Subscription
from app.detection.severity import (
    compute_severity,
    normalize_mrr,
    urgency_from_amount,
    urgency_from_churn_score,
    urgency_from_days,
)
from app.detection.rules import (
    detect_r1_failed_payment,
    detect_r2_stalled_suspension,
    detect_r3_duplicate_charge,
    detect_r5_at_risk,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# MRR Normalization Tests
# ---------------------------------------------------------------------------

class TestNormalizeMRR:
    def test_monthly_plan_returns_price(self):
        assert normalize_mrr(Decimal("29.99"), "MONTH") == Decimal("29.99")

    def test_annual_plan_divides_by_12(self):
        result = normalize_mrr(Decimal("120.00"), "YEAR")
        assert result == Decimal("10.00")

    def test_annual_plan_299_99(self):
        result = normalize_mrr(Decimal("299.99"), "YEAR")
        # 299.99 / 12 ≈ 24.999...
        assert abs(result - Decimal("24.999166")) < Decimal("0.001")

    def test_zero_price(self):
        assert normalize_mrr(Decimal("0"), "MONTH") == Decimal("0")

    def test_case_insensitive_year(self):
        result = normalize_mrr(Decimal("120.00"), "year")
        assert result == Decimal("10.00")


# ---------------------------------------------------------------------------
# Severity Tests
# ---------------------------------------------------------------------------

class TestComputeSeverity:
    def test_zero_mrr_zero_urgency_gives_zero(self):
        assert compute_severity(Decimal("0"), 0.0) == 0

    def test_max_mrr_max_urgency_gives_100(self):
        assert compute_severity(Decimal("500"), 1.0) == 100

    def test_high_mrr_no_urgency(self):
        # mrr=300 (60% of 500), urgency=0 → 60% of 60 = 36
        result = compute_severity(Decimal("300"), 0.0)
        assert result == 36

    def test_no_mrr_high_urgency(self):
        # mrr=0, urgency=1 → 40
        result = compute_severity(Decimal("0"), 1.0)
        assert result == 40

    def test_half_mrr_half_urgency(self):
        # mrr=250, urgency=0.5 → 30 + 20 = 50
        result = compute_severity(Decimal("250"), 0.5)
        assert result == 50

    def test_severity_capped_at_100(self):
        result = compute_severity(Decimal("99999"), 1.0)
        assert result == 100

    def test_severity_minimum_zero(self):
        result = compute_severity(Decimal("-10"), -1.0)
        assert result == 0

    def test_custom_max_mrr_reference(self):
        result = compute_severity(Decimal("100"), 0.0, max_mrr_reference=Decimal("100"))
        assert result == 60


class TestUrgencyHelpers:
    def test_urgency_from_days_zero(self):
        assert urgency_from_days(0) == 0.0

    def test_urgency_from_days_at_max(self):
        assert urgency_from_days(30, max_days=30) == 1.0

    def test_urgency_from_days_over_max(self):
        assert urgency_from_days(60, max_days=30) == 1.0

    def test_urgency_from_days_half(self):
        assert urgency_from_days(15, max_days=30) == 0.5

    def test_urgency_from_churn_clamped(self):
        assert urgency_from_churn_score(1.5) == 1.0
        assert urgency_from_churn_score(-0.1) == 0.0

    def test_urgency_from_amount_zero(self):
        assert urgency_from_amount(Decimal("0")) == 0.0

    def test_urgency_from_amount_at_max(self):
        assert urgency_from_amount(Decimal("500"), Decimal("500")) == 1.0


# ---------------------------------------------------------------------------
# Rule Tests
# ---------------------------------------------------------------------------

class TestR1FailedPayment:
    def test_detects_suspended_subscription(
        self, db: Session, suspended_subscription: Subscription
    ):
        cases = detect_r1_failed_payment(db)
        sub_ids = [c.subscription_id for c in cases]
        assert suspended_subscription.id in sub_ids

    def test_does_not_flag_active_subscription(
        self, db: Session, active_subscription: Subscription
    ):
        cases = detect_r1_failed_payment(db)
        sub_ids = [c.subscription_id for c in cases]
        assert active_subscription.id not in sub_ids

    def test_detects_failed_payment_event(
        self, db: Session, active_subscription: Subscription
    ):
        payment = Payment(
            paypal_txn_id="TXN-FAIL-001",
            subscription_id=active_subscription.id,
            amount=Decimal("29.99"),
            currency="USD",
            status="FAILED",
            occurred_at=_utcnow() - timedelta(days=2),
            source="real",
        )
        db.add(payment)
        db.flush()

        cases = detect_r1_failed_payment(db)
        sub_ids = [c.subscription_id for c in cases]
        assert active_subscription.id in sub_ids

    def test_no_duplicate_cases_on_rerun(
        self, db: Session, suspended_subscription: Subscription
    ):
        cases1 = detect_r1_failed_payment(db)
        cases2 = detect_r1_failed_payment(db)
        # Should not create new rows on second run
        all_open = db.query(Case).filter_by(
            subscription_id=suspended_subscription.id, type="FAILED_PAYMENT"
        ).count()
        assert all_open == 1

    def test_severity_positive(
        self, db: Session, suspended_subscription: Subscription
    ):
        cases = detect_r1_failed_payment(db)
        for c in cases:
            assert c.severity > 0


class TestR2StalledSuspension:
    def test_detects_stalled_suspension(
        self, db: Session, suspended_subscription: Subscription
    ):
        # suspended_subscription has suspended_at = 10 days ago (> default 7)
        cases = detect_r2_stalled_suspension(db)
        sub_ids = [c.subscription_id for c in cases]
        assert suspended_subscription.id in sub_ids

    def test_does_not_flag_recently_suspended(
        self, db: Session, sample_plan: Plan, sample_subscriber: Subscriber
    ):
        sub = Subscription(
            paypal_subscription_id="I-NEWSUSP",
            subscriber_id=sample_subscriber.id,
            plan_id=sample_plan.id,
            status="SUSPENDED",
            start_time=_utcnow() - timedelta(days=30),
            suspended_at=_utcnow() - timedelta(days=2),  # only 2 days ago
            source="real",
        )
        db.add(sub)
        db.flush()

        cases = detect_r2_stalled_suspension(db)
        sub_ids = [c.subscription_id for c in cases]
        assert sub.id not in sub_ids

    def test_case_type_correct(
        self, db: Session, suspended_subscription: Subscription
    ):
        cases = detect_r2_stalled_suspension(db)
        for c in cases:
            assert c.type == "STALLED_SUSPENSION"


class TestR3DuplicateCharge:
    def test_detects_duplicate_within_window(
        self, db: Session, active_subscription: Subscription
    ):
        amount = Decimal("29.99")
        now = _utcnow()
        p1 = Payment(
            paypal_txn_id="TXN-DUP-A",
            subscription_id=active_subscription.id,
            amount=amount,
            currency="USD",
            status="COMPLETED",
            occurred_at=now - timedelta(hours=1),
            source="real",
        )
        p2 = Payment(
            paypal_txn_id="TXN-DUP-B",
            subscription_id=active_subscription.id,
            amount=amount,
            currency="USD",
            status="COMPLETED",
            occurred_at=now - timedelta(hours=2),
            source="real",
        )
        db.add_all([p1, p2])
        db.flush()

        cases = detect_r3_duplicate_charge(db)
        assert len(cases) > 0

    def test_no_flag_for_single_payment(
        self, db: Session, active_subscription: Subscription
    ):
        p1 = Payment(
            paypal_txn_id="TXN-SINGLE",
            subscription_id=active_subscription.id,
            amount=Decimal("29.99"),
            currency="USD",
            status="COMPLETED",
            occurred_at=_utcnow(),
            source="real",
        )
        db.add(p1)
        db.flush()

        cases = detect_r3_duplicate_charge(db)
        assert len(cases) == 0


class TestR5AtRisk:
    def test_detects_high_churn_score(
        self, db: Session, active_subscription: Subscription
    ):
        cs = ChurnScore(
            subscription_id=active_subscription.id,
            score=0.85,
            features_json="{}",
            model_version="v1.0",
        )
        db.add(cs)
        db.flush()

        cases = detect_r5_at_risk(db)
        sub_ids = [c.subscription_id for c in cases]
        assert active_subscription.id in sub_ids

    def test_does_not_flag_low_churn_score(
        self, db: Session, active_subscription: Subscription
    ):
        cs = ChurnScore(
            subscription_id=active_subscription.id,
            score=0.30,
            features_json="{}",
            model_version="v1.0",
        )
        db.add(cs)
        db.flush()

        cases = detect_r5_at_risk(db)
        sub_ids = [c.subscription_id for c in cases]
        assert active_subscription.id not in sub_ids

    def test_only_flags_active_subscriptions(
        self, db: Session, suspended_subscription: Subscription
    ):
        cs = ChurnScore(
            subscription_id=suspended_subscription.id,
            score=0.90,
            features_json="{}",
            model_version="v1.0",
        )
        db.add(cs)
        db.flush()

        cases = detect_r5_at_risk(db)
        sub_ids = [c.subscription_id for c in cases]
        assert suspended_subscription.id not in sub_ids

    def test_case_type_at_risk(
        self, db: Session, active_subscription: Subscription
    ):
        cs = ChurnScore(
            subscription_id=active_subscription.id,
            score=0.80,
            features_json="{}",
            model_version="v1.0",
        )
        db.add(cs)
        db.flush()

        cases = detect_r5_at_risk(db)
        for c in cases:
            assert c.type == "AT_RISK"

