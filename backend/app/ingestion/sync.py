"""Sync subscriptions and backfill transaction history from PayPal."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Plan, SyncState, Subscription
from app.db.session import db_session
from app.ingestion.normalizer import (
    upsert_payment,
    upsert_plan,
    upsert_subscriber,
    upsert_subscription,
)
from app.paypal import client as pp
from app.paypal.schemas import PayPalSubscription, TransactionRecord

logger = logging.getLogger(__name__)

_SYNC_KEY_LAST_BACKFILL = "last_backfill_at"


def _get_sync_value(db: Session, key: str) -> Optional[str]:
    row = db.query(SyncState).filter_by(key=key).first()
    return row.value if row else None


def _set_sync_value(db: Session, key: str, value: str) -> None:
    row = db.query(SyncState).filter_by(key=key).first()
    if row:
        row.value = value
    else:
        db.add(SyncState(key=key, value=value))
    db.flush()


def sync_plans(db: Session) -> list[Plan]:
    """Fetch all plans from PayPal and upsert into local DB."""
    plans_data = pp.list_plans(page_size=100)
    plans_list = plans_data.get("plans", [])
    result: list[Plan] = []
    for p in plans_list:
        try:
            pp_plan = pp.get_plan(p["id"])
            plan = upsert_plan(db, pp_plan)
            result.append(plan)
        except Exception as exc:
            logger.warning("Failed to sync plan %s: %s", p.get("id"), exc)
    db.commit()
    logger.info("Synced %d plans", len(result))
    return result


def sync_subscriptions_for_plan(db: Session, plan: Plan, max_pages: int = 10) -> int:
    """Sync all subscriptions for a given plan. Returns count of upserted subscriptions."""
    count = 0
    for page in range(1, max_pages + 1):
        try:
            data = pp.list_subscriptions(
                plan_id=plan.paypal_plan_id, page=page, page_size=20
            )
        except Exception as exc:
            logger.warning(
                "list_subscriptions page %d for plan %s failed: %s",
                page, plan.paypal_plan_id, exc,
            )
            break

        subscriptions = data.get("subscriptions", [])
        if not subscriptions:
            break

        for sub_stub in subscriptions:
            sub_id = sub_stub.get("id")
            if not sub_id:
                continue
            try:
                pp_sub = pp.get_subscription(sub_id)
                _upsert_subscription_from_paypal(db, pp_sub, plan)
                count += 1
            except Exception as exc:
                logger.warning("Failed to sync subscription %s: %s", sub_id, exc)

        if len(subscriptions) < 20:
            break

    db.commit()
    return count


def _upsert_subscription_from_paypal(
    db: Session, pp_sub: PayPalSubscription, plan: Plan
) -> Subscription:
    """Normalize and upsert a PayPal subscription into local tables."""
    sub_info = pp_sub.subscriber
    payer_id: Optional[str] = None
    email = "unknown@example.com"
    name = ""

    if sub_info:
        payer_id = sub_info.payer_id
        email = sub_info.email_address or email
        if sub_info.name:
            given = sub_info.name.get("given_name", "")
            surname = sub_info.name.get("surname", "")
            name = f"{given} {surname}".strip()

    subscriber = upsert_subscriber(db, payer_id, email, name, source="real")
    return upsert_subscription(db, pp_sub, plan, subscriber, source="real")


def backfill_transactions(
    db: Session,
    days: int = 90,
    force: bool = False,
) -> int:
    """
    Backfill payment transactions from PayPal's transaction search API.
    Returns total number of transactions upserted.
    """
    now = datetime.now(timezone.utc)

    if not force:
        last = _get_sync_value(db, _SYNC_KEY_LAST_BACKFILL)
        if last:
            last_dt = datetime.fromisoformat(last)
            if (now - last_dt).total_seconds() < 3600:
                logger.info("Skipping backfill – ran less than 1 hour ago")
                return 0

    start_date = now - timedelta(days=days)
    total = 0
    page = 1

    while True:
        try:
            search_resp = pp.search_transactions(
                start_date=start_date,
                end_date=now,
                page=page,
                page_size=100,
            )
        except Exception as exc:
            logger.error("Transaction search page %d failed: %s", page, exc)
            break

        for txn_record in search_resp.transaction_details:
            try:
                _upsert_transaction(db, txn_record)
                total += 1
            except Exception as exc:
                ti = txn_record.transaction_info
                logger.warning(
                    "Failed to upsert transaction %s: %s",
                    ti.transaction_id, exc,
                )

        db.commit()

        if search_resp.total_pages is None or page >= search_resp.total_pages:
            break
        page += 1

    _set_sync_value(db, _SYNC_KEY_LAST_BACKFILL, now.isoformat())
    db.commit()
    logger.info("Backfill complete: %d transactions processed", total)
    return total


def _upsert_transaction(db: Session, txn_record: TransactionRecord) -> None:
    """Try to link a transaction record to a known subscription."""
    cart = txn_record.cart_info or {}
    # PayPal embeds the subscription ID in cart_info.item_details or billing_agreement_id
    sub_paypal_id: Optional[str] = None

    resource = getattr(txn_record, "cart_info", None) or {}
    # Also check transaction_info for billing_agreement_id
    ti = txn_record.transaction_info

    # Try to find billing agreement from cart info
    item_details = cart.get("item_details", [])
    for item in item_details:
        ba_id = item.get("billing_agreement_id")
        if ba_id:
            sub_paypal_id = ba_id
            break

    if not sub_paypal_id:
        # Try direct field
        sub_paypal_id = cart.get("billing_agreement_id")

    subscription: Optional[Subscription] = None
    if sub_paypal_id:
        subscription = (
            db.query(Subscription).filter_by(paypal_subscription_id=sub_paypal_id).first()
        )

    if subscription is None:
        # Can't link – skip
        return

    upsert_payment(db, subscription, txn_record, source="real")


def run_full_sync(days: int = 90) -> dict[str, int]:
    """Run full plan + subscription + transaction sync. Returns summary counts."""
    counts: dict[str, int] = {"plans": 0, "subscriptions": 0, "transactions": 0}
    with db_session() as db:
        plans = sync_plans(db)
        counts["plans"] = len(plans)
        for plan in plans:
            n = sync_subscriptions_for_plan(db, plan)
            counts["subscriptions"] += n
        counts["transactions"] = backfill_transactions(db, days=days)
    return counts

