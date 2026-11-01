"""Pydantic models for PayPal API payloads."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------
class Money(BaseModel):
    currency_code: str
    value: Decimal


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------
class BillingCycle(BaseModel):
    sequence: int
    tenure_type: str  # REGULAR | TRIAL
    total_cycles: int = 0
    pricing_scheme: Optional[dict[str, Any]] = None
    frequency: Optional[dict[str, Any]] = None


class PaymentPreferences(BaseModel):
    auto_bill_outstanding: bool = True
    setup_fee_failure_action: str = "CONTINUE"
    payment_failure_threshold: int = 3


class PayPalPlan(BaseModel):
    id: str
    product_id: Optional[str] = None
    name: str
    status: str = "ACTIVE"
    billing_cycles: list[BillingCycle] = Field(default_factory=list)
    payment_preferences: Optional[PaymentPreferences] = None
    quantity_supported: bool = False
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None


class SubscriberInfo(BaseModel):
    payer_id: Optional[str] = None
    email_address: Optional[str] = None
    name: Optional[dict[str, Any]] = None


class SubscriptionShippingAddress(BaseModel):
    name: Optional[dict[str, Any]] = None
    address: Optional[dict[str, Any]] = None


class PayPalSubscription(BaseModel):
    id: str
    plan_id: str
    status: str
    start_time: Optional[datetime] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    subscriber: Optional[SubscriberInfo] = None
    billing_info: Optional[dict[str, Any]] = None
    plan: Optional[dict[str, Any]] = None
    quantity: Optional[str] = None
    shipping_amount: Optional[Money] = None


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------
class TransactionFees(BaseModel):
    paypal_fee: Optional[Money] = None
    gross_amount: Optional[Money] = None
    net_amount: Optional[Money] = None


class TransactionInfo(BaseModel):
    transaction_id: Optional[str] = None
    transaction_status: Optional[str] = None
    transaction_amount: Optional[Money] = None
    fee_amount: Optional[Money] = None
    transaction_initiation_date: Optional[datetime] = None
    transaction_updated_date: Optional[datetime] = None


class PayerInfo(BaseModel):
    account_id: Optional[str] = None
    email_address: Optional[str] = None
    payer_name: Optional[dict[str, Any]] = None


class TransactionRecord(BaseModel):
    transaction_info: TransactionInfo
    payer_info: Optional[PayerInfo] = None
    cart_info: Optional[dict[str, Any]] = None


class TransactionSearchResponse(BaseModel):
    transaction_details: list[TransactionRecord] = Field(default_factory=list)
    account_number: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    last_refreshed_datetime: Optional[datetime] = None
    page: int = 1
    total_items: Optional[int] = None
    total_pages: Optional[int] = None


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------
class WebhookResourceAmount(BaseModel):
    total: Optional[str] = None
    currency: Optional[str] = None


class WebhookResource(BaseModel):
    id: Optional[str] = None
    plan_id: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[WebhookResourceAmount] = None
    billing_agreement_id: Optional[str] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    custom_id: Optional[str] = None
    # Extra fields captured dynamically
    model_config = {"extra": "allow"}


class PayPalWebhookEvent(BaseModel):
    id: str
    event_type: str
    event_version: Optional[str] = None
    resource_type: Optional[str] = None
    resource: Optional[WebhookResource] = None
    summary: Optional[str] = None
    create_time: Optional[datetime] = None
    links: Optional[list[dict[str, Any]]] = None

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------
class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str
    app_id: Optional[str] = None
    expires_in: int
    nonce: Optional[str] = None
    scope: Optional[str] = None

