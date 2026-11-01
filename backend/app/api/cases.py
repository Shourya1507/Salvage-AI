"""Cases router: GET/POST /api/cases"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Case, Proposal
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _case_to_dict(case: Case) -> dict:
    proposals = [
        {
            "id": p.id,
            "action_type": p.action_type,
            "diagnosis": p.diagnosis,
            "confidence": float(p.confidence),
            "status": p.status,
            "created_at": p.created_at.isoformat(),
        }
        for p in case.proposals
    ]
    return {
        "id": case.id,
        "subscription_id": case.subscription_id,
        "type": case.type,
        "status": case.status,
        "severity": case.severity,
        "mrr_at_risk": float(case.mrr_at_risk),
        "evidence": json.loads(case.evidence_json or "{}"),
        "opened_at": case.opened_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "proposals": proposals,
    }


@router.get("")
def list_cases(
    status: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
) -> dict:
    """Return a paginated list of cases."""
    query = db.query(Case)
    if status:
        query = query.filter(Case.status == status)
    if type:
        query = query.filter(Case.type == type)
    total = query.count()
    cases = query.order_by(Case.severity.desc(), Case.opened_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "cases": [_case_to_dict(c) for c in cases],
    }


@router.get("/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)) -> dict:
    """Return a single case with full detail."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return _case_to_dict(case)


@router.post("/{case_id}/run-agent")
def run_agent_for_case(
    case_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """(Re)generate a proposal for a case by running the LLM agent."""
    from app.agent.runner import run_agent  # lazy import to avoid slow anthropic import at module load

    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    if case.status not in ("open", "proposed", "needs_review"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot run agent on case with status '{case.status}'",
        )

    try:
        agent_output = run_agent(db, case)
    except Exception as exc:
        logger.error("Agent failed for case %s: %s", case_id, exc)
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    # Create proposal row
    proposal = Proposal(
        case_id=case.id,
        diagnosis=agent_output.diagnosis,
        reasoning=agent_output.reasoning,
        action_type=agent_output.action_type.value,
        params_json=json.dumps(agent_output.params),
        customer_message=agent_output.customer_message,
        confidence=float(agent_output.confidence),
        model=settings.llm_model,
        status="pending",
    )
    db.add(proposal)
    case.status = "proposed"
    db.commit()

    return {
        "proposal_id": proposal.id,
        "action_type": proposal.action_type,
        "diagnosis": proposal.diagnosis,
        "reasoning": proposal.reasoning,
        "confidence": float(proposal.confidence),
        "customer_message": proposal.customer_message,
        "params": agent_output.params,
        "status": proposal.status,
    }

