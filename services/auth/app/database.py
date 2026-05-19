from __future__ import annotations
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event, text
from .config import get_settings
import structlog

log = structlog.get_logger(__name__)
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
            echo=settings.environment == "development",
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _SessionLocal


async def get_db_session():
    """FastAPI dependency that yields a tenant-scoped DB session."""
    async with get_session_factory()() as session:
        yield session


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """
    Set the RLS session variable so PostgreSQL row-level security
    policies filter to the correct tenant.
    """
    await session.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))
