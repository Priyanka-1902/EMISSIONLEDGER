"""
EmissionLedger Auth Service
FastAPI application — Cognito JWT validation, user management, RBAC.
"""
from __future__ import annotations
import structlog
import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .config import get_settings
from .routers import users, tenants, health

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("auth_service.starting", environment=settings.environment)
    yield
    log.info("auth_service.stopping")


def create_app() -> FastAPI:
    settings = get_settings()

    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
        )

    app = FastAPI(
        title="EmissionLedger Auth Service",
        version="1.0.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Request-ID"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(users.router, prefix="/v1/users", tags=["users"])
    app.include_router(tenants.router, prefix="/v1/tenants", tags=["tenants"])

    FastAPIInstrumentor.instrument_app(app)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    return app


app = create_app()
