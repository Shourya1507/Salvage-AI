"""
Create a sandbox PayPal product and billing plans.

Usage:
    cd backend
    python -m scripts.create_plans
"""
from __future__ import annotations

import json
import logging
import sys
import os

# Allow running from backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.paypal.client import _auth_headers, _get_access_token
from app.config import settings

import httpx

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def create_product(name: str, description: str) -> dict:
    """Create a PayPal product (catalog item)."""
    payload = {
        "name": name,
        "description": description,
        "type": "SERVICE",
        "category": "SOFTWARE",
    }
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{settings.paypal_base_url}/v1/catalogs/products",
            headers=_auth_headers(),
            json=payload,
        )
        resp.raise_for_status()
    data = resp.json()
    logger.info("Created product: %s (id=%s)", data.get("name"), data.get("id"))
    return data


def create_plan(
    product_id: str,
    name: str,
    description: str,
    price: str,
    currency: str,
    interval_unit: str,
    interval_count: int,
) -> dict:
    """Create a billing plan."""
    payload = {
        "product_id": product_id,
        "name": name,
        "description": description,
        "status": "ACTIVE",
        "billing_cycles": [
            {
                "frequency": {
                    "interval_unit": interval_unit,
                    "interval_count": interval_count,
                },
                "tenure_type": "REGULAR",
                "sequence": 1,
                "total_cycles": 0,  # infinite
                "pricing_scheme": {
                    "fixed_price": {
                        "value": price,
                        "currency_code": currency,
                    }
                },
            }
        ],
        "payment_preferences": {
            "auto_bill_outstanding": True,
            "setup_fee_failure_action": "CONTINUE",
            "payment_failure_threshold": 3,
        },
    }
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{settings.paypal_base_url}/v1/billing/plans",
            headers=_auth_headers(),
            json=payload,
        )
        resp.raise_for_status()
    data = resp.json()
    logger.info("Created plan: %s (id=%s)", data.get("name"), data.get("id"))
    return data


def main() -> None:
    logger.info("Using PayPal env: %s", settings.paypal_env)
    settings.validate_live_credentials()

    # Create product
    product = create_product(
        name="Salvage AI SaaS",
        description="AI-powered revenue recovery for subscription businesses",
    )
    product_id = product["id"]

    # Create monthly plan
    monthly_plan = create_plan(
        product_id=product_id,
        name="Salvage AI - Monthly",
        description="Monthly subscription to Salvage AI",
        price="29.99",
        currency="USD",
        interval_unit="MONTH",
        interval_count=1,
    )

    # Create annual plan
    annual_plan = create_plan(
        product_id=product_id,
        name="Salvage AI - Annual",
        description="Annual subscription to Salvage AI (2 months free)",
        price="299.99",
        currency="USD",
        interval_unit="YEAR",
        interval_count=1,
    )

    result = {
        "product_id": product_id,
        "monthly_plan_id": monthly_plan["id"],
        "annual_plan_id": annual_plan["id"],
    }
    print("\n=== Created PayPal Resources ===")
    print(json.dumps(result, indent=2))
    print("\nAdd these to your .env file!")


if __name__ == "__main__":
    main()

