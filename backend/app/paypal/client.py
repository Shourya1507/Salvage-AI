"""PayPal HTTP client with OAuth token caching."""
from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import httpx

from app.config import settings
from app.paypal.schemas import (
    OAuthTokenResponse,
    PayPalPlan,
    PayPalSubscription,
    PayPalWebhookEvent,
    TransactionSearchResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token cache (process-level, good enough for a single worker)
# ---------------------------------------------------------------------------
_token_cache: dict[str, Any] = {
    "access_token": None,
    "expires_at": 0.0,
}


def _basic_auth() -> str:
    raw = f"{settings.paypal_client_id}:{settings.paypal_client_secret}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


def _get_access_token() -> str:
    """Return a valid access token, refreshing if needed."""
    now = time.time()
    if _token_cache["access_token"] and _token_cache["expires_at"] > now + 30:
        return _token_cache["access_token"]  # type: ignore[return-value]

    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{settings.paypal_base_url}/v1/oauth2/token",
            headers={
                "Authorization": _basic_auth(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()

    token_data = OAuthTokenResponse.model_validate(resp.json())
    _token_cache["access_token"] = token_data.access_token
    _token_cache["expires_at"] = now + token_data.expires_in
    logger.info("PayPal OAuth token refreshed")
    return token_data.access_token


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_access_token()}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Public client functions
# ---------------------------------------------------------------------------

def get_subscription(subscription_id: str) -> PayPalSubscription:
    """Fetch a single subscription by ID."""
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{settings.paypal_base_url}/v1/billing/subscriptions/{subscription_id}",
            headers=_auth_headers(),
        )
        resp.raise_for_status()
    return PayPalSubscription.model_validate(resp.json())


def list_subscriptions(
    plan_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """List subscriptions (sandbox has limited filtering)."""
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if plan_id:
        params["plan_id"] = plan_id
    if status:
        params["status"] = status

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{settings.paypal_base_url}/v1/billing/subscriptions",
            headers=_auth_headers(),
            params=params,
        )
        resp.raise_for_status()
    return resp.json()


def get_plan(plan_id: str) -> PayPalPlan:
    """Fetch a billing plan by ID."""
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{settings.paypal_base_url}/v1/billing/plans/{plan_id}",
            headers=_auth_headers(),
        )
        resp.raise_for_status()
    return PayPalPlan.model_validate(resp.json())


def list_plans(product_id: Optional[str] = None, page_size: int = 20) -> dict[str, Any]:
    """List billing plans."""
    params: dict[str, Any] = {"page_size": page_size, "total_required": "true"}
    if product_id:
        params["product_id"] = product_id

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{settings.paypal_base_url}/v1/billing/plans",
            headers=_auth_headers(),
            params=params,
        )
        resp.raise_for_status()
    return resp.json()


def search_transactions(
    start_date: datetime,
    end_date: datetime,
    transaction_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
) -> TransactionSearchResponse:
    """Search transactions via the Reporting API."""
    params: dict[str, Any] = {
        "start_date": start_date.strftime("%Y-%m-%dT%H:%M:%S-0000"),
        "end_date": end_date.strftime("%Y-%m-%dT%H:%M:%S-0000"),
        "page": page,
        "page_size": page_size,
        "fields": "all",
    }
    if transaction_status:
        params["transaction_status"] = transaction_status

    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{settings.paypal_base_url}/v1/reporting/transactions",
            headers=_auth_headers(),
            params=params,
        )
        resp.raise_for_status()
    return TransactionSearchResponse.model_validate(resp.json())


def get_subscription_transactions(
    subscription_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> dict[str, Any]:
    """Get transactions for a subscription."""
    params: dict[str, Any] = {}
    if start_time:
        params["start_time"] = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    if end_time:
        params["end_time"] = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{settings.paypal_base_url}/v1/billing/subscriptions/{subscription_id}/transactions",
            headers=_auth_headers(),
            params=params,
        )
        resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Mutating actions (only called from executor)
# ---------------------------------------------------------------------------

def capture_subscription_payment(subscription_id: str, note: str = "Retry payment") -> dict[str, Any]:
    """Capture outstanding balance for a subscription."""
    with httpx.Client(timeout=20) as client:
        resp = client.post(
            f"{settings.paypal_base_url}/v1/billing/subscriptions/{subscription_id}/capture",
            headers=_auth_headers(),
            json={"note": note, "capture_type": "OUTSTANDING_BALANCE", "amount": {"currency_code": "USD", "value": "0"}},
        )
        resp.raise_for_status()
    return resp.json() if resp.text else {}


def activate_subscription(subscription_id: str, reason: str = "Reactivating subscription") -> None:
    """Activate a suspended subscription."""
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{settings.paypal_base_url}/v1/billing/subscriptions/{subscription_id}/activate",
            headers=_auth_headers(),
            json={"reason": reason},
        )
        resp.raise_for_status()


def suspend_subscription(subscription_id: str, reason: str = "Suspended by Salvage AI") -> None:
    """Suspend an active subscription."""
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{settings.paypal_base_url}/v1/billing/subscriptions/{subscription_id}/suspend",
            headers=_auth_headers(),
            json={"reason": reason},
        )
        resp.raise_for_status()


def cancel_subscription(subscription_id: str, reason: str = "Cancelled by Salvage AI") -> None:
    """Cancel a subscription."""
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{settings.paypal_base_url}/v1/billing/subscriptions/{subscription_id}/cancel",
            headers=_auth_headers(),
            json={"reason": reason},
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Webhook verification
# ---------------------------------------------------------------------------

def verify_webhook_signature(
    auth_algo: str,
    cert_url: str,
    transmission_id: str,
    transmission_sig: str,
    transmission_time: str,
    webhook_id: str,
    raw_body: bytes,
) -> bool:
    """Verify a webhook signature using PayPal's verification endpoint."""
    payload = {
        "auth_algo": auth_algo,
        "cert_url": cert_url,
        "transmission_id": transmission_id,
        "transmission_sig": transmission_sig,
        "transmission_time": transmission_time,
        "webhook_id": webhook_id,
        "webhook_event": raw_body.decode("utf-8"),
    }
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{settings.paypal_base_url}/v1/notifications/verify-webhook-signature",
                headers=_auth_headers(),
                json=payload,
            )
            resp.raise_for_status()
        result = resp.json()
        return result.get("verification_status") == "SUCCESS"
    except httpx.HTTPStatusError as exc:
        logger.warning("Webhook verification HTTP error: %s", exc)
        return False
    except httpx.RequestError as exc:
        logger.warning("Webhook verification request error: %s", exc)
        return False


def check_auth_reachability() -> bool:
    """Return True if we can obtain a PayPal access token."""
    try:
        _get_access_token()
        return True
    except Exception:
        return False

