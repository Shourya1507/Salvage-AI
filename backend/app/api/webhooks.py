"""Webhook receiver: POST /webhooks/paypal"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.ingestion.normalizer import record_webhook_event, upsert_subscriber, upsert_subscription
from app.paypal import client as pp
from app.paypal.schemas import PayPalWebhookEvent

logger = logging.getLogger(__name__)

router = APIRouter()


def _process_webhook_event(event: PayPalWebhookEvent, db: Session) -> None:
    """Process a PayPal webhook event and trigger relevant side effects."""
    from app.db.models import Plan, Subscription
    from app.detection.rules import run_all_rules

    resource = event.resource
    if resource is None:
        return

    et = event.event_type

    if et in (
        "BILLING.SUBSCRIPTION.SUSPENDED",
        "BILLING.SUBSCRIPTION.PAYMENT.FAILED",
    ):
        sub_id = resource.id
        if sub_id:
            sub = db.query(Subscription).filter_by(paypal_subscription_id=sub_id).first()
            if sub:
                sub.status = "SUSPENDED"
                if sub.suspended_at is None:
                    sub.suspended_at = datetime.now(timezone.utc)
                db.flush()

    elif et == "BILLING.SUBSCRIPTION.CANCELLED":
        sub_id = resource.id
        if sub_id:
            sub = db.query(Subscription).filter_by(paypal_subscription_id=sub_id).first()
            if sub:
                sub.status = "CANCELLED"
                if sub.cancelled_at is None:
                    sub.cancelled_at = datetime.now(timezone.utc)
                db.flush()

    elif et == "BILLING.SUBSCRIPTION.ACTIVATED":
        sub_id = resource.id
        if sub_id:
            sub = db.query(Subscription).filter_by(paypal_subscription_id=sub_id).first()
            if sub:
                sub.status = "ACTIVE"
                sub.suspended_at = None
                db.flush()

    elif et == "BILLING.SUBSCRIPTION.CREATED":
        # Try to fetch and upsert subscription
        sub_id = resource.id
        plan_id_str = resource.plan_id
        if sub_id and plan_id_str:
            try:
                pp_sub = pp.get_subscription(sub_id)
                plan = db.query(Plan).filter_by(paypal_plan_id=plan_id_str).first()
                if plan and pp_sub.subscriber:
                    sub_info = pp_sub.subscriber
                    subscriber = upsert_subscriber(
                        db,
                        sub_info.payer_id,
                        sub_info.email_address or "unknown@example.com",
                        source="real",
                    )
                    upsert_subscription(db, pp_sub, plan, subscriber, source="real")
                    db.flush()
            except Exception as exc:
                logger.warning("Failed to upsert subscription from webhook: %s", exc)

    # Run detection rules after state changes
    try:
        run_all_rules(db)
    except Exception as exc:
        logger.error("Detection rules failed after webhook: %s", exc)


@router.post("/webhooks/paypal")
async def receive_paypal_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    paypal_auth_algo: str = Header(default="", alias="paypal-auth-algo"),
    paypal_cert_url: str = Header(default="", alias="paypal-cert-url"),
    paypal_transmission_id: str = Header(default="", alias="paypal-transmission-id"),
    paypal_transmission_sig: str = Header(default="", alias="paypal-transmission-sig"),
    paypal_transmission_time: str = Header(default="", alias="paypal-transmission-time"),
) -> dict:
    raw_body = await request.body()

    # Parse payload
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    try:
        event = PayPalWebhookEvent.model_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {exc}") from exc

    # Verify signature
    verified = False
    if settings.webhook_verify:
        if not settings.paypal_webhook_id:
            raise HTTPException(
                status_code=500,
                detail="PAYPAL_WEBHOOK_ID not configured",
            )
        verified = pp.verify_webhook_signature(
            auth_algo=paypal_auth_algo,
            cert_url=paypal_cert_url,
            transmission_id=paypal_transmission_id,
            transmission_sig=paypal_transmission_sig,
            transmission_time=paypal_transmission_time,
            webhook_id=settings.paypal_webhook_id,
            raw_body=raw_body,
        )
        if not verified:
            logger.warning(
                "Webhook signature verification FAILED for event %s type=%s",
                event.id,
                event.event_type,
            )
            raise HTTPException(status_code=401, detail="Webhook signature verification failed")
    else:
        # Demo mode: skip verification but mark unverified
        verified = False
        logger.debug("Webhook verification disabled (WEBHOOK_VERIFY=false)")

    # Record event (idempotency check)
    event_row, is_new = record_webhook_event(db, event, raw_body, verified=verified)

    if not is_new:
        logger.info("Duplicate webhook event %s – ignoring", event.id)
        db.commit()
        return {"status": "duplicate", "event_id": event.id}

    # Process event
    try:
        _process_webhook_event(event, db)
        event_row.processed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        logger.error("Failed to process webhook event %s: %s", event.id, exc)
        db.rollback()
        raise HTTPException(status_code=500, detail="Event processing failed") from exc

    return {"status": "ok", "event_id": event.id}

