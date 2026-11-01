"""SQLAlchemy ORM models for Salvage AI."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# subscribers
# ---------------------------------------------------------------------------
class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    paypal_payer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="real")  # real|simulated
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="subscriber", lazy="select"
    )


# ---------------------------------------------------------------------------
# plans
# ---------------------------------------------------------------------------
class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    paypal_plan_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)  # MONTH|YEAR
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="plan", lazy="select"
    )


# ---------------------------------------------------------------------------
# subscriptions
# ---------------------------------------------------------------------------
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    paypal_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    subscriber_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscribers.id"), nullable=False
    )
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="real")

    subscriber: Mapped["Subscriber"] = relationship(back_populates="subscriptions")
    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="subscription", lazy="select"
    )
    cases: Mapped[list["Case"]] = relationship(
        back_populates="subscription", lazy="select"
    )
    churn_scores: Mapped[list["ChurnScore"]] = relationship(
        back_populates="subscription", lazy="select"
    )


# ---------------------------------------------------------------------------
# payments
# ---------------------------------------------------------------------------
class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    paypal_txn_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    subscription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscriptions.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="real")

    subscription: Mapped["Subscription"] = relationship(back_populates="payments")


# ---------------------------------------------------------------------------
# webhook_events
# ---------------------------------------------------------------------------
class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    paypal_event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------
class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    subscription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscriptions.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    # FAILED_PAYMENT|STALLED_SUSPENSION|DUPLICATE|PRICE_FALLOUT|AT_RISK
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open"
    )
    # open|proposed|resolved|dismissed|needs_review
    severity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mrr_at_risk: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    subscription: Mapped["Subscription"] = relationship(back_populates="cases")
    proposals: Mapped[list["Proposal"]] = relationship(
        back_populates="case", lazy="select"
    )


# ---------------------------------------------------------------------------
# proposals
# ---------------------------------------------------------------------------
class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id"), nullable=False
    )
    diagnosis: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    customer_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.0)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    # pending|approved|dismissed|executed|failed
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    edited_params_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    case: Mapped["Case"] = relationship(back_populates="proposals")
    action_logs: Mapped[list["ActionLog"]] = relationship(
        back_populates="proposal", lazy="select"
    )


# ---------------------------------------------------------------------------
# action_log
# ---------------------------------------------------------------------------
class ActionLog(Base):
    __tablename__ = "action_log"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_action_log_proposal"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    proposal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("proposals.id"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    request_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    response_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    recovered_mrr: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)

    proposal: Mapped["Proposal"] = relationship(back_populates="action_logs")


# ---------------------------------------------------------------------------
# churn_scores
# ---------------------------------------------------------------------------
class ChurnScore(Base):
    __tablename__ = "churn_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    subscription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscriptions.id"), nullable=False
    )
    score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    features_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    subscription: Mapped["Subscription"] = relationship(back_populates="churn_scores")


# ---------------------------------------------------------------------------
# sync_state
# ---------------------------------------------------------------------------
class SyncState(Base):
    __tablename__ = "sync_state"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")

