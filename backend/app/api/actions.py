"""Actions router: GET /api/actions"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.models import ActionLog
from app.db.session import get_db

router = APIRouter(prefix="/api/actions", tags=["actions"])


def _log_to_dict(log: ActionLog) -> dict:
    return {
        "id": log.id,
        "proposal_id": log.proposal_id,
        "action_type": log.action_type,
        "success": log.success,
        "executed_at": log.executed_at.isoformat(),
        "recovered_mrr": float(log.recovered_mrr) if log.recovered_mrr else None,
        "request": json.loads(log.request_json or "{}"),
        "response": json.loads(log.response_json or "{}"),
    }


@router.get("")
def list_actions(
    success: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
) -> dict:
    """Return a paginated action log."""
    query = db.query(ActionLog)
    if success is not None:
        query = query.filter(ActionLog.success == success)
    total = query.count()
    logs = query.order_by(ActionLog.executed_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "actions": [_log_to_dict(lg) for lg in logs],
    }

