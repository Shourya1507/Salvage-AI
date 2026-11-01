"""Pydantic output validation schema for agent proposals."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class ActionType(str, Enum):
    RETRY_PAYMENT = "RETRY_PAYMENT"
    REACTIVATE_SUBSCRIPTION = "REACTIVATE_SUBSCRIPTION"
    SUSPEND_SUBSCRIPTION = "SUSPEND_SUBSCRIPTION"
    CANCEL_SUBSCRIPTION = "CANCEL_SUBSCRIPTION"
    SEND_DUNNING_MESSAGE = "SEND_DUNNING_MESSAGE"
    WIN_BACK_OFFER = "WIN_BACK_OFFER"
    REVIEW_DUPLICATE_FOR_REFUND = "REVIEW_DUPLICATE_FOR_REFUND"
    NO_ACTION = "NO_ACTION"


class AgentOutput(BaseModel):
    """Validated output from the LLM agent."""

    diagnosis: str = Field(..., min_length=1, description="Plain-language summary of the issue")
    reasoning: str = Field(..., min_length=1, description="Step-by-step reasoning citing evidence")
    action_type: ActionType = Field(..., description="Recommended action")
    params: dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    customer_message: str = Field(default="", description="Message to send the customer")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in recommendation")

    @field_validator("diagnosis", "reasoning", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("customer_message", mode="before")
    @classmethod
    def customer_message_strip(cls, v: Optional[str]) -> str:
        return (v or "").strip()

