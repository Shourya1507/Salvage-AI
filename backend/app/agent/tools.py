"""Read-only tools available to the LLM agent."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _serialize(obj: Any) -> Any:
    """JSON-serializable helper."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def get_subscription_timeline(db: Session, subscription_id: str) -> dict[str, Any]:
    """
    Return payments and status changes for a subscription.
    Tool: read-only.
    """
    from app.db.models import Payment, Subscription

    sub = db.query(Subscription).get(subscription_id)
    if not sub:
        return {"error": f"Subscription {subscription_id} not found"}

    payments = (
        db.query(Payment)
        .filter_by(subscription_id=subscription_id)
        .order_by(Payment.occurred_at)
        .all()
    )

    timeline = {
        "subscription_id": subscription_id,
        "paypal_subscription_id": sub.paypal_subscription_id,
        "status": sub.status,
        "start_time": sub.start_time.isoformat() if sub.start_time else None,
        "suspended_at": sub.suspended_at.isoformat() if sub.suspended_at else None,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
        "payments": [
            {
                "id": p.id,
                "paypal_txn_id": p.paypal_txn_id,
                "amount": str(p.amount),
                "currency": p.currency,
                "status": p.status,
                "occurred_at": p.occurred_at.isoformat(),
            }
            for p in payments
        ],
    }
    return timeline


def get_plan(db: Session, plan_id: str) -> dict[str, Any]:
    """
    Return plan details including price, interval.
    Tool: read-only.
    """
    from app.db.models import Plan

    plan = db.query(Plan).get(plan_id)
    if not plan:
        return {"error": f"Plan {plan_id} not found"}

    return {
        "plan_id": plan_id,
        "paypal_plan_id": plan.paypal_plan_id,
        "name": plan.name,
        "interval": plan.interval,
        "price": str(plan.price),
        "currency": plan.currency,
        "active": plan.active,
    }


def get_cohort_stats(db: Session, plan_id: str, window_days: int = 90) -> dict[str, Any]:
    """
    Return cancellation/failure rates for a plan cohort within the given window.
    Tool: read-only.
    """
    from app.db.models import Plan, Subscription

    plan = db.query(Plan).get(plan_id)
    if not plan:
        return {"error": f"Plan {plan_id} not found"}

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    subs = (
        db.query(Subscription)
        .filter_by(plan_id=plan_id)
        .filter(Subscription.start_time >= cutoff)
        .all()
    )

    total = len(subs)
    if total == 0:
        return {
            "plan_id": plan_id,
            "window_days": window_days,
            "total": 0,
            "cancelled": 0,
            "suspended": 0,
            "active": 0,
            "cancellation_rate": 0.0,
            "failure_rate": 0.0,
        }

    cancelled = sum(1 for s in subs if s.status == "CANCELLED")
    suspended = sum(1 for s in subs if s.status in ("SUSPENDED", "PAYMENT_FAILURE"))
    active = sum(1 for s in subs if s.status == "ACTIVE")

    return {
        "plan_id": plan_id,
        "plan_name": plan.name,
        "window_days": window_days,
        "total": total,
        "cancelled": cancelled,
        "suspended": suspended,
        "active": active,
        "cancellation_rate": round(cancelled / total, 4),
        "failure_rate": round(suspended / total, 4),
    }


def get_churn_score(db: Session, subscription_id: str) -> dict[str, Any]:
    """
    Return the latest churn score and top features for a subscription.
    Tool: read-only.
    """
    from app.db.models import ChurnScore

    score_row = (
        db.query(ChurnScore)
        .filter_by(subscription_id=subscription_id)
        .order_by(ChurnScore.scored_at.desc())
        .first()
    )

    if not score_row:
        return {
            "subscription_id": subscription_id,
            "score": None,
            "message": "No churn score available. Run scoring first.",
        }

    features = json.loads(score_row.features_json) if score_row.features_json else {}
    return {
        "subscription_id": subscription_id,
        "score": float(score_row.score),
        "model_version": score_row.model_version,
        "scored_at": score_row.scored_at.isoformat(),
        "top_features": features,
    }


def get_similar_resolved_cases(db: Session, case_type: str, limit: int = 5) -> dict[str, Any]:
    """
    Return prior resolved cases of the same type with their accepted proposals.
    Tool: read-only.
    """
    from app.db.models import Case, Proposal

    resolved_cases = (
        db.query(Case)
        .filter_by(type=case_type, status="resolved")
        .order_by(Case.updated_at.desc())
        .limit(limit)
        .all()
    )

    results = []
    for case in resolved_cases:
        approved_proposals = [
            p for p in case.proposals if p.status in ("approved", "executed")
        ]
        for prop in approved_proposals:
            results.append({
                "case_id": case.id,
                "case_type": case.type,
                "severity": case.severity,
                "mrr_at_risk": str(case.mrr_at_risk),
                "proposal_diagnosis": prop.diagnosis,
                "action_type": prop.action_type,
                "confidence": float(prop.confidence),
                "resolved_at": case.updated_at.isoformat(),
            })

    return {
        "case_type": case_type,
        "resolved_examples": results[:limit],
    }


# ---------------------------------------------------------------------------
# Tool definitions for Anthropic tool-use API
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "get_subscription_timeline",
        "description": (
            "Returns the payment history and status changes (active, suspended, cancelled) "
            "for a given subscription. Use this to understand what happened to a subscription over time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {
                    "type": "string",
                    "description": "The local subscription UUID",
                }
            },
            "required": ["subscription_id"],
        },
    },
    {
        "name": "get_plan",
        "description": (
            "Returns plan details: name, price, interval (MONTH or YEAR), currency, and whether it's active."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "The local plan UUID",
                }
            },
            "required": ["plan_id"],
        },
    },
    {
        "name": "get_cohort_stats",
        "description": (
            "Returns aggregated cancellation and failure rates for all subscriptions "
            "on a given plan within a time window. Use this to detect price-change fallout."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "The local plan UUID",
                },
                "window_days": {
                    "type": "integer",
                    "description": "Number of days to look back (default 90)",
                    "default": 90,
                },
            },
            "required": ["plan_id"],
        },
    },
    {
        "name": "get_churn_score",
        "description": (
            "Returns the ML churn risk score (0-1) and the top contributing features "
            "for a given subscription."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {
                    "type": "string",
                    "description": "The local subscription UUID",
                }
            },
            "required": ["subscription_id"],
        },
    },
    {
        "name": "get_similar_resolved_cases",
        "description": (
            "Returns previously resolved cases of the same type with the actions that were approved. "
            "Use this to inform your recommendation with historical precedent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "case_type": {
                    "type": "string",
                    "description": "One of: FAILED_PAYMENT, STALLED_SUSPENSION, DUPLICATE, PRICE_FALLOUT, AT_RISK",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of examples to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["case_type"],
        },
    },
]


def dispatch_tool(db: Session, tool_name: str, tool_input: dict) -> Any:
    """Dispatch a tool call to the appropriate function."""
    if tool_name == "get_subscription_timeline":
        return get_subscription_timeline(db, tool_input["subscription_id"])
    elif tool_name == "get_plan":
        return get_plan(db, tool_input["plan_id"])
    elif tool_name == "get_cohort_stats":
        return get_cohort_stats(
            db,
            tool_input["plan_id"],
            window_days=tool_input.get("window_days", 90),
        )
    elif tool_name == "get_churn_score":
        return get_churn_score(db, tool_input["subscription_id"])
    elif tool_name == "get_similar_resolved_cases":
        return get_similar_resolved_cases(
            db,
            tool_input["case_type"],
            limit=tool_input.get("limit", 5),
        )
    else:
        return {"error": f"Unknown tool: {tool_name}"}

