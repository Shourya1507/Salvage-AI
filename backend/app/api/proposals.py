"""Proposals router: POST /api/proposals/{id}/approve|dismiss"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Proposal
from app.db.session import get_db
from app.executor.service import ExecutorError, execute_proposal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


def _require_admin(x_admin_token: str = Header(default="", alias="x-admin-token")) -> str:
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return x_admin_token


class ApproveRequest(BaseModel):
    edited_params: Optional[dict[str, Any]] = None
    decided_by: Optional[str] = None


class DismissRequest(BaseModel):
    reason: str = "Dismissed by merchant"
    decided_by: Optional[str] = None


@router.get("/{proposal_id}")
def get_proposal(proposal_id: str, db: Session = Depends(get_db)) -> dict:
    """Return a single proposal by ID."""
    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return {
        "id": proposal.id,
        "case_id": proposal.case_id,
        "action_type": proposal.action_type,
        "diagnosis": proposal.diagnosis,
        "reasoning": proposal.reasoning,
        "customer_message": proposal.customer_message,
        "confidence": float(proposal.confidence),
        "params": json.loads(proposal.params_json or "{}"),
        "status": proposal.status,
        "created_at": proposal.created_at.isoformat(),
        "decided_at": proposal.decided_at.isoformat() if proposal.decided_at else None,
        "decided_by": proposal.decided_by,
        "model": proposal.model,
    }


@router.post("/{proposal_id}/approve")
def approve_proposal(
    proposal_id: str,
    body: ApproveRequest,
    db: Session = Depends(get_db),
    admin_token: str = Depends(_require_admin),
) -> dict:
    """Approve a proposal and immediately execute it."""
    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    if proposal.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Proposal is not pending (status={proposal.status})",
        )

    now = datetime.now(timezone.utc)
    proposal.status = "approved"
    proposal.decided_at = now
    proposal.decided_by = body.decided_by or "admin"

    if body.edited_params is not None:
        proposal.edited_params_json = json.dumps(body.edited_params)

    db.flush()

    try:
        log = execute_proposal(db, proposal_id)
    except ExecutorError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.error("Execution failed for proposal %s: %s", proposal_id, exc)
        raise HTTPException(status_code=500, detail=f"Execution error: {exc}") from exc

    return {
        "proposal_id": proposal_id,
        "proposal_status": proposal.status,
        "action_log_id": log.id,
        "success": log.success,
        "executed_at": log.executed_at.isoformat(),
        "recovered_mrr": float(log.recovered_mrr) if log.recovered_mrr else None,
    }


@router.post("/{proposal_id}/dismiss")
def dismiss_proposal(
    proposal_id: str,
    body: DismissRequest,
    db: Session = Depends(get_db),
    admin_token: str = Depends(_require_admin),
) -> dict:
    """Dismiss a pending proposal."""
    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    if proposal.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Proposal is not pending (status={proposal.status})",
        )

    now = datetime.now(timezone.utc)
    proposal.status = "dismissed"
    proposal.decided_at = now
    proposal.decided_by = body.decided_by or "admin"

    # Revert case status to needs_review
    case = proposal.case
    case.status = "needs_review"
    case.updated_at = now

    db.commit()

    return {
        "proposal_id": proposal_id,
        "status": "dismissed",
        "reason": body.reason,
        "decided_at": now.isoformat(),
    }

