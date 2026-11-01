"""FastAPI application entry point."""
from __future__ import annotations

import logging
import sys
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.session import init_db

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup checks
    logger.info("Starting Salvage AI backend...")

    # Guard: refuse live credentials unless explicitly allowed
    settings.validate_live_credentials()

    # Create DB tables
    init_db()
    logger.info("Database initialized")

    yield

    logger.info("Salvage AI backend shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Salvage AI",
    description="AI agent that detects and fixes revenue leaks in PayPal subscription businesses",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_request_id(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------------------
# Exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/healthz", tags=["health"])
def health_check() -> dict:
    """Check DB, PayPal auth, and LLM reachability."""
    from app.db.session import SessionLocal
    from app.paypal.client import check_auth_reachability

    # DB check
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)

    # PayPal check
    paypal_ok = False
    try:
        paypal_ok = check_auth_reachability()
    except Exception as exc:
        logger.warning("PayPal health check failed: %s", exc)

    # LLM check
    llm_ok = False
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.llm_api_key)
        # Just instantiating is enough to verify the key is set
        llm_ok = bool(settings.llm_api_key)
    except Exception as exc:
        logger.warning("LLM health check failed: %s", exc)

    status = "healthy" if (db_ok and paypal_ok and llm_ok) else "degraded"

    return {
        "status": status,
        "db": "ok" if db_ok else "error",
        "paypal": "ok" if paypal_ok else "error",
        "llm": "ok" if llm_ok else "error",
        "demo_mode": settings.demo_mode,
        "executor_enabled": settings.executor_enabled,
        "paypal_env": settings.paypal_env,
    }


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from app.api.webhooks import router as webhooks_router
from app.api.sync import router as sync_router
from app.api.dashboard import router as dashboard_router
from app.api.cases import router as cases_router
from app.api.proposals import router as proposals_router
from app.api.actions import router as actions_router
from app.api.demo import router as demo_router

app.include_router(webhooks_router)
app.include_router(sync_router)
app.include_router(dashboard_router)
app.include_router(cases_router)
app.include_router(proposals_router)
app.include_router(actions_router)
app.include_router(demo_router)

