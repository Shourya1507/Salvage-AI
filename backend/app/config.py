"""Application configuration via environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # PayPal
    paypal_client_id: str = Field(..., description="PayPal OAuth client ID")
    paypal_client_secret: str = Field(..., description="PayPal OAuth client secret")
    paypal_env: Literal["sandbox", "live"] = "sandbox"
    paypal_webhook_id: str = Field(default="", description="PayPal webhook ID for verification")

    @property
    def paypal_base_url(self) -> str:
        if self.paypal_env == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"

    # Webhook
    webhook_verify: bool = True

    # LLM
    llm_api_key: str = Field(..., description="Anthropic API key")
    llm_model: str = "claude-3-5-sonnet-20241022"

    # Database
    database_url: str = "sqlite:///./salvage.db"

    # App modes
    demo_mode: bool = False
    executor_enabled: bool = True
    allow_live: bool = False

    # Security
    admin_token: str = Field(..., description="Bearer token for admin routes")

    # Detection thresholds
    stalled_days: int = 7
    churn_threshold: float = 0.7
    duplicate_window_hours: int = 72

    # Agent
    agent_max_tool_calls: int = 6
    agent_timeout_seconds: int = 60

    @field_validator("paypal_env")
    @classmethod
    def check_live_allowed(cls, v: str, info: object) -> str:
        # Will be checked again at startup with full settings context
        return v

    def validate_live_credentials(self) -> None:
        """Raise if live PayPal is requested without the explicit allow flag."""
        if self.paypal_env == "live" and not self.allow_live:
            raise RuntimeError(
                "paypal_env=live requires ALLOW_LIVE=true. "
                "Set ALLOW_LIVE=true only when you intend to use production credentials."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()

