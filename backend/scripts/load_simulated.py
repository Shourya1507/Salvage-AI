"""
Load simulated data into the database (non-demo mode utility).
Useful for seeding test data without enabling DEMO_MODE.

Usage:
    cd backend
    python -m scripts.load_simulated
"""
from __future__ import annotations

import json
import logging
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.db.session import db_session, init_db
from app.db.models import (
    ChurnScore,
    Payment,
    Plan,
    Subscriber,
    Subscription,
)
from app.detection.rules import run_all_rules

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def load_simulated(
    plan_count: int = 2,
    subscriber_count: int = 20,
) -> dict:
    """Load simulated data and run detection rules. Returns summary."""
    init_db()

    counts: dict[str, int] = {"plans": 0, "subscribers": 0, "subscriptions": 0, "payments": 0}

    with db_session() as db:
        # Create plans
        plans: list[Plan] = []
        for i in range(plan_count):
            interval = "MONTH" if i % 2 == 0 else "YEAR"
            price = Decimal(str(round(random.uniform(9.99, 99.99), 2)))
            plan = Plan(
                paypal_plan_id=f"SIM-PLAN-{uuid.uuid4().hex[:8].upper()}",
                name=f"Simulated Plan {i + 1} ({interval})",
                interval=interval,
                price=price,
                currency="USD",
                active=True,
            )
            db.add(plan)
            plans.append(plan)
        db.flush()
        counts["plans"] = len(plans)

        statuses = ["ACTIVE"] * 6 + ["SUSPENDED"] * 2 + ["CANCELLED"] * 2
        all_subs: list[Subscription] = []

        for i in range(subscriber_count):
            subscriber = Subscriber(
                email=f"sim_user_{i}_{uuid.uuid4().hex[:6]}@example.com",
                name=f"Simulated User {i}",
                source="simulated",
            )
            db.add(subscriber)
            db.flush()
            counts["subscribers"] += 1

            plan = random.choice(plans)
            status = random.choice(statuses)
            start = _utcnow() - timedelta(days=random.randint(30, 365))
            suspended_at = None
            cancelled_at = None

            if status == "SUSPENDED":
                suspended_at = _utcnow() - timedelta(days=random.randint(1, 30))
            elif status == "CANCELLED":
                cancelled_at = _utcnow() - timedelta(days=random.randint(1, 60))

            sub = Subscription(
                paypal_subscription_id=f"I-SIM-{uuid.uuid4().hex[:12].upper()}",
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
            all_subs.append(sub)
            counts["subscriptions"] += 1

            # Payments
            payment_count = random.randint(1, 6)
            for j in range(payment_count):
                p_status = random.choice(["COMPLETED"] * 3 + ["FAILED"])
                occurred = start + timedelta(days=30 * j)
                if occurred > _utcnow():
                    break
                payment = Payment(
                    paypal_txn_id=f"SIM-TXN-{uuid.uuid4().hex[:12].upper()}",
                    subscription_id=sub.id,
                    amount=plan.price,
                    currency="USD",
                    status=p_status,
                    occurred_at=occurred,
                    source="simulated",
                )
                db.add(payment)
                counts["payments"] += 1

            # Churn score
            score = round(random.uniform(0.05, 0.95), 4)
            cs = ChurnScore(
                subscription_id=sub.id,
                score=score,
                features_json=json.dumps({
                    "tenure_months": ((_utcnow() - start).days / 30),
                    "monthly_charge": float(plan.price) if plan.interval == "MONTH" else float(plan.price) / 12,
                    "contract_type": 1.0 if plan.interval == "YEAR" else 0.0,
                }),
                model_version="v1.0-simulated",
            )
            db.add(cs)

        db.flush()

        # Run detection rules
        rule_counts = run_all_rules(db)
        logger.info("Detection results: %s", rule_counts)

    logger.info("Simulated data loaded: %s", counts)
    return counts


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Load simulated data")
    parser.add_argument("--plans", type=int, default=2)
    parser.add_argument("--subscribers", type=int, default=20)
    args = parser.parse_args()

    result = load_simulated(plan_count=args.plans, subscriber_count=args.subscribers)
    print(json.dumps(result, indent=2))

