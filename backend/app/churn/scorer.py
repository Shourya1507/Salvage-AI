"""Churn scorer: load trained model, score subscribers."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "churn_model.pkl"
_MODEL_VERSION = "v1.0"

# Lazy-loaded model
_model: Any = None
_feature_names: list[str] = []


def _load_model() -> Any:
    global _model, _feature_names
    if _model is not None:
        return _model

    if not _MODEL_PATH.exists():
        logger.warning("Churn model not found at %s. Run scripts/train_churn.py first.", _MODEL_PATH)
        return None

    try:
        import joblib
        bundle = joblib.load(_MODEL_PATH)
        _model = bundle["model"]
        _feature_names = bundle.get("feature_names", [])
        logger.info("Churn model loaded from %s (version %s)", _MODEL_PATH, bundle.get("version", "?"))
    except Exception as exc:
        logger.error("Failed to load churn model: %s", exc)
        _model = None

    return _model


def _extract_features(subscription: Any, db: Session) -> dict[str, float]:
    """Extract numeric features from a Subscription for scoring."""
    from app.db.models import Payment

    now = datetime.now(timezone.utc)

    # Tenure in months
    start = subscription.start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    tenure_months = max((now - start).days / 30, 0)

    # Monthly charge
    plan = subscription.plan
    if plan.interval.upper() == "YEAR":
        monthly_charge = float(plan.price) / 12
    else:
        monthly_charge = float(plan.price)

    # Contract type: 0=monthly, 1=annual
    contract_type = 1 if plan.interval.upper() == "YEAR" else 0

    # Count failed payments
    payments = db.query(Payment).filter_by(subscription_id=subscription.id).all()
    count_failed = sum(1 for p in payments if p.status in ("FAILED", "DENIED", "REVERSED"))
    total_payments = len(payments)

    # Payment method (proxy: 0=unknown, 1=paypal_balance, 2=card)
    payment_method = 1  # assume PayPal balance for now

    return {
        "tenure_months": tenure_months,
        "monthly_charge": monthly_charge,
        "contract_type": float(contract_type),
        "payment_method": float(payment_method),
        "count_failed_payments": float(count_failed),
        "total_payments": float(total_payments),
        "failure_rate": float(count_failed) / max(total_payments, 1),
    }


def score_subscription(db: Session, subscription: Any) -> Optional[dict[str, Any]]:
    """
    Score a subscription for churn risk.
    Returns dict with score, features, and top contributing features.
    Returns None if model is not available.
    """
    model = _load_model()
    if model is None:
        return None

    import numpy as np

    features = _extract_features(subscription, db)

    # Build feature vector in the same order as training
    feature_order = _feature_names or [
        "tenure_months",
        "monthly_charge",
        "contract_type",
        "payment_method",
        "count_failed_payments",
        "total_payments",
        "failure_rate",
    ]
    X = np.array([[features.get(f, 0.0) for f in feature_order]])

    try:
        proba = model.predict_proba(X)[0]
        score = float(proba[1])  # probability of churn (class=1)
    except Exception as exc:
        logger.error("Model predict_proba failed: %s", exc)
        return None

    # Top contributing features (based on absolute coefficient or feature importance)
    top_features: dict[str, float] = {}
    try:
        if hasattr(model, "coef_"):
            # Logistic Regression
            importances = model.coef_[0]
        elif hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        else:
            importances = None

        if importances is not None:
            paired = sorted(
                zip(feature_order, importances), key=lambda x: abs(x[1]), reverse=True
            )
            top_features = {
                feat: round(float(features.get(feat, 0.0)) * float(imp), 4)
                for feat, imp in paired[:5]
            }
    except Exception:
        pass

    return {
        "score": round(score, 4),
        "features": features,
        "top_features": top_features,
        "model_version": _MODEL_VERSION,
    }


def score_all_active_subscriptions(db: Session) -> int:
    """Score all active subscriptions and persist ChurnScore rows. Returns count."""
    from app.db.models import ChurnScore, Subscription

    now = datetime.now(timezone.utc)
    active_subs = db.query(Subscription).filter_by(status="ACTIVE").all()
    count = 0

    for sub in active_subs:
        result = score_subscription(db, sub)
        if result is None:
            continue

        row = ChurnScore(
            subscription_id=sub.id,
            score=result["score"],
            features_json=json.dumps(result["features"]),
            model_version=result["model_version"],
            scored_at=now,
        )
        db.add(row)
        count += 1

    db.commit()
    logger.info("Scored %d subscriptions for churn", count)
    return count

