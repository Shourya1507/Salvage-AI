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
            "case_id": p.case_id,
            "action_type": p.action_type,
            "diagnosis": p.diagnosis,
            "reasoning": p.reasoning,
            "customer_message": p.customer_message,
            "params": json.loads(p.params_json or "{}"),
            "confidence": float(p.confidence),
            "model": p.model,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "decided_at": p.decided_at.isoformat() if p.decided_at else None,
            "decided_by": p.decided_by,
        }
        for p in (case.proposals or [])
    ]

    sub_dict = None
    subscriber_dict = None
    plan_dict = None

    sub = case.subscription
    if sub:
        sub_dict = {
            "id": sub.id,
            "paypal_subscription_id": sub.paypal_subscription_id,
            "status": sub.status,
            "source": sub.source,
            "start_time": sub.start_time.isoformat() if sub.start_time else None,
        }
        if sub.subscriber:
            subscriber_dict = {
                "id": sub.subscriber.id,
                "name": sub.subscriber.name,
                "email": sub.subscriber.email,
                "source": sub.subscriber.source,
            }
        if sub.plan:
            plan_dict = {
                "id": sub.plan.id,
                "name": sub.plan.name,
                "price": float(sub.plan.price),
                "currency": sub.plan.currency,
                "interval": sub.plan.interval,
            }

    return {
        "id": case.id,
        "subscription_id": case.subscription_id,
        "type": case.type,
        "status": case.status,
        "severity": case.severity,
        "mrr_at_risk": float(case.mrr_at_risk),
        "evidence": json.loads(case.evidence_json or "{}"),
        "opened_at": case.opened_at.isoformat() if case.opened_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        "proposals": proposals,
        "subscription": sub_dict,
        "subscriber": subscriber_dict,
        "plan": plan_dict,
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

