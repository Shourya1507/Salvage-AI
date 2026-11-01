"""Severity scoring and MRR normalization for detection rules."""
from __future__ import annotations

from decimal import Decimal


def normalize_mrr(price: Decimal, interval: str) -> Decimal:
    """
    Compute Monthly Recurring Revenue (MRR) from a plan's price and interval.

    Args:
        price: The plan price (Decimal).
        interval: 'MONTH' or 'YEAR'.

    Returns:
        Monthly equivalent revenue as Decimal.
    """
    if interval.upper() == "YEAR":
        return price / Decimal("12")
    # Default: MONTH
    return price


def compute_severity(
    mrr_at_risk: Decimal,
    urgency: float,
    max_mrr_reference: Decimal = Decimal("500"),
) -> int:
    """
    Compute a 0-100 severity score from MRR at risk and urgency.

    Formula:
        mrr_component  = min(mrr_at_risk / max_mrr_reference, 1.0) * 60
        urgency_component = urgency * 40
        severity = round(mrr_component + urgency_component)

    Args:
        mrr_at_risk: MRR value at risk (Decimal, USD).
        urgency: 0.0-1.0 normalised urgency factor.
        max_mrr_reference: Ceiling MRR that maps to full mrr_component.

    Returns:
        Integer severity in range [0, 100].
    """
    if mrr_at_risk < Decimal("0"):
        mrr_at_risk = Decimal("0")

    urgency = max(0.0, min(1.0, urgency))

    mrr_ratio = float(mrr_at_risk) / float(max_mrr_reference)
    mrr_ratio = min(mrr_ratio, 1.0)

    mrr_component = mrr_ratio * 60.0
    urgency_component = urgency * 40.0

    raw = mrr_component + urgency_component
    return max(0, min(100, round(raw)))


def urgency_from_days(days_overdue: float, max_days: float = 30.0) -> float:
    """
    Convert days overdue into a 0-1 urgency factor.
    Saturates at max_days.
    """
    if days_overdue <= 0:
        return 0.0
    return min(days_overdue / max_days, 1.0)


def urgency_from_churn_score(churn_score: float) -> float:
    """Convert a churn score (0-1) directly to urgency (0-1)."""
    return max(0.0, min(1.0, float(churn_score)))


def urgency_from_amount(amount: Decimal, max_amount: Decimal = Decimal("500")) -> float:
    """Convert an absolute amount into urgency (for duplicate charge risk)."""
    if amount <= Decimal("0"):
        return 0.0
    return min(float(amount) / float(max_amount), 1.0)

