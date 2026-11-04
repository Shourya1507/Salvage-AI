"""Sync router: POST /api/sync/backfill"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.ingestion.sync import run_full_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _require_admin(x_admin_token: str = Header(default="", alias="x-admin-token")) -> None:
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")


@router.post("/run")
@router.post("/backfill")
def trigger_backfill(
    days: int = 90,
    _: None = Depends(_require_admin),
) -> dict:
    """Trigger a full sync: plans → subscriptions → transactions."""
    try:
        counts = run_full_sync(days=days)
    except Exception as exc:
        logger.error("Backfill failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "ok", "counts": counts}

