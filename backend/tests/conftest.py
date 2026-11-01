"""Test fixtures and configuration."""
from __future__ import annotations

import os
import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Generator

# Set env vars BEFORE importing app modules
os.environ.setdefault("PAYPAL_CLIENT_ID", "test_client_id")
os.environ.setdefault("PAYPAL_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("PAYPAL_WEBHOOK_ID", "test_webhook_id")
os.environ.setdefault("LLM_API_KEY", "test_llm_key")
os.environ.setdefault("ADMIN_TOKEN", "test_admin_token")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("WEBHOOK_VERIFY", "false")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.models import Base, Plan, Subscriber, Subscription, Payment, Case, Proposal, ChurnScore


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Provide a clean in-memory SQLite session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def sample_plan(db: Session) -> Plan:
    plan = Plan(
        paypal_plan_id="P-TESTPLAN001",
        name="Monthly Test Plan",
        interval="MONTH",
        price=Decimal("29.99"),
        currency="USD",
        active=True,
    )
    db.add(plan)
    db.flush()
    return plan


@pytest.fixture
def sample_annual_plan(db: Session) -> Plan:
    plan = Plan(
        paypal_plan_id="P-TESTPLAN002",
        name="Annual Test Plan",
        interval="YEAR",
        price=Decimal("299.99"),
        currency="USD",
        active=True,
    )
    db.add(plan)
    db.flush()
    return plan


@pytest.fixture
def sample_subscriber(db: Session) -> Subscriber:
    sub = Subscriber(
        paypal_payer_id="PAYER-001",
        email="test@example.com",
        name="Test User",
        source="real",
    )
    db.add(sub)
    db.flush()
    return sub


@pytest.fixture
def active_subscription(db: Session, sample_plan: Plan, sample_subscriber: Subscriber) -> Subscription:
    sub = Subscription(
        paypal_subscription_id="I-ACTIVE001",
        subscriber_id=sample_subscriber.id,
        plan_id=sample_plan.id,
        status="ACTIVE",
        start_time=_utcnow() - timedelta(days=60),
        source="real",
    )
    db.add(sub)
    db.flush()
    return sub


@pytest.fixture
def suspended_subscription(db: Session, sample_plan: Plan, sample_subscriber: Subscriber) -> Subscription:
    sub = Subscription(
        paypal_subscription_id="I-SUSP001",
        subscriber_id=sample_subscriber.id,
        plan_id=sample_plan.id,
        status="SUSPENDED",
        start_time=_utcnow() - timedelta(days=90),
        suspended_at=_utcnow() - timedelta(days=10),
        source="real",
    )
    db.add(sub)
    db.flush()
    return sub

