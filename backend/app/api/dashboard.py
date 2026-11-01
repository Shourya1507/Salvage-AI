"""Dashboard router: GET /api/dashboard"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import ActionLog, Case
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)) -> dict:
    """
    Return totals:
    - MRR at risk grouped by case type
    - Total MRR recovered (from action_log)
    - Open case count by status
    """
    # MRR at risk by type (open or proposed cases only)
    mrr_by_type_rows = (
        db.query(Case.type, func.sum(Case.mrr_at_risk))
        .filter(Case.status.in_(["open", "proposed"]))
        .group_by(Case.type)
        .all()
    )
    mrr_by_type = {row[0]: float(row[1] or 0) for row in mrr_by_type_rows}

    total_mrr_at_risk = sum(mrr_by_type.values())

    # Total recovered MRR from successful action logs
    recovered_row = (
        db.query(func.sum(ActionLog.recovered_mrr))
        .filter(ActionLog.success == True)  # noqa: E712
        .scalar()
    )
    total_recovered = float(recovered_row or 0)

    # Case counts by status
    status_counts_rows = (
        db.query(Case.status, func.count(Case.id))
        .group_by(Case.status)
        .all()
    )
    status_counts = {row[0]: row[1] for row in status_counts_rows}

    # Total open cases
    total_open = status_counts.get("open", 0) + status_counts.get("proposed", 0)

    # Case counts by type
    type_counts_rows = (
        db.query(Case.type, func.count(Case.id))
        .filter(Case.status.in_(["open", "proposed"]))
        .group_by(Case.type)
        .all()
    )
    type_counts = {row[0]: row[1] for row in type_counts_rows}

    return {
        "total_mrr_at_risk": round(total_mrr_at_risk, 2),
        "total_recovered_mrr": round(total_recovered, 2),
        "mrr_at_risk_by_type": {k: round(v, 2) for k, v in mrr_by_type.items()},
        "open_cases": total_open,
        "case_counts_by_status": status_counts,
        "case_counts_by_type": type_counts,
    }

